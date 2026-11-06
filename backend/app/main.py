import json
import logging
import os
import threading
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field
from typing import Callable, Literal, Optional as Opt

from app import config
from app.agent.llm import AgentLLM, OpenAICompatibleLLM
from app.agent.prompts import VALID_MODES
from app.agent.runner import run_agent
from app.agent.sse import SSE_HEADERS, stream_events
from app.agent_store import AgentStore, DEFAULT_AGENT_ID, effective_mode
from app.document import KnowledgeBase, get_embeddings, load_and_split
from app.qa import NOT_FOUND_ANSWER, QAService, get_llm
from app.seed_agents import ensure_seed_agents
from app.security import RateLimiter, client_key, require_admin

_feedback_lock = threading.Lock()


def _append_feedback(path: str, line: str, max_bytes: int) -> None:
    """追加一行反馈；超过上限时把当前文件轮转成 .1（覆盖旧的 .1）。

    磁盘占用最多约 2 倍上限：主文件 + 一个归档。
    """
    with _feedback_lock:
        if max_bytes > 0 and os.path.exists(path) and os.path.getsize(path) >= max_bytes:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

READ_BLOCK = 1024 * 1024
DOC_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MISSING_KEY_MSG = "服务未配置 OPENAI_API_KEY，暂时无法上传和问答"

logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    agent_id: str = Field(DEFAULT_AGENT_ID, max_length=32)


class HistoryTurn(BaseModel):
    """一轮历史消息。只用于把追问改写成独立问题，不进入研究与回答阶段。"""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class AgentRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    agent_id: str = Field(DEFAULT_AGENT_ID, max_length=32)
    # 请求级模式覆盖（评测用）：传了就覆盖专家配置
    answer_mode: Opt[Literal["strict", "reference"]] = None
    # 多轮：最近几轮对话（按时间正序），只用于把追问改写成独立问题
    history: List[HistoryTurn] = Field(default_factory=list, max_length=12)


class AgentCreateRequest(BaseModel):
    """新建专家。name 必填，其余可选；agent_id 可自定义（合法时）。"""
    name: str = Field(..., min_length=1, max_length=40)
    description: str = Field("", max_length=200)
    persona: str = Field("", max_length=2000)
    greeting: str = Field("", max_length=200)
    emoji: str = Field("", max_length=8)
    model: str = Field("", max_length=100)
    agent_id: str = Field("", max_length=32)
    answer_mode: Literal["strict", "reference"] = "reference"
    starter_questions: List[str] = Field(default_factory=list, max_length=4)


class FeedbackRequest(BaseModel):
    """回答点赞/点踩反馈：仅记录，不改变任何业务状态。"""
    agent_id: str = Field(DEFAULT_AGENT_ID, max_length=32)
    question: str = Field(..., min_length=1, max_length=1000)
    answer: str = Field(..., min_length=1, max_length=8000)
    rating: Literal["up", "down"]
    reason: str = Field("", max_length=500)
    mode: Optional[str] = None
    grounded_ratio: Optional[float] = Field(None, ge=0, le=1)


def _safe_display_name(filename: Optional[str]) -> str:
    """仅用于展示：去掉目录部分（兼容 Windows 路径），不参与落盘路径。"""
    name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    return name[:200] or "unnamed"


def create_app(
    embeddings: Optional[Embeddings] = None,
    llm: Optional[BaseChatModel] = None,
    upload_dir: str = config.UPLOAD_DIR,
    index_dir: str = config.FAISS_DIR,
    max_upload_mb: int = config.MAX_UPLOAD_MB,
    agent_llm: Optional[AgentLLM] = None,
    agent_max_steps: int = config.AGENT_MAX_STEPS,
    agent_log_dir: Optional[str] = config.AGENT_LOG_DIR,
    agents_dir: Optional[str] = None,
    seed_builtin: bool = True,
    agent_llm_factory: Opt[Callable[[str], AgentLLM]] = None,
) -> FastAPI:
    """应用工厂：生产环境用默认参数；测试时注入假的 embeddings / llm 和临时目录。

    agents_dir 是多专家存储根目录（None 时用 AGENTS_DIR 配置）。
    seed_builtin=False 时测试里不播种内置专家。
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal agent_log_dir
        os.makedirs(upload_dir, exist_ok=True)
        app.state.kb = app.state.qa = app.state.agent_llm = None
        app.state.store = None
        if embeddings is None and not config.OPENAI_API_KEY:
            # 不阻止启动：健康检查照常可用，上传/问答返回 503
            logger.warning(MISSING_KEY_MSG)
        else:
            emb = embeddings or get_embeddings()
            kb = KnowledgeBase(index_dir, emb)
            app.state.kb = kb
            qa_llm = llm or get_llm()
            app.state.qa_llm = qa_llm
            app.state.qa = QAService(kb, qa_llm)
            # Agent 用独立模型（需要稳定的 tools 调用能力），与固定 RAG 分开配置。
            # 没配 Key 时保持 None，/api/agent/stream 会返回 503；
            # 不能在这里无条件构造客户端，否则未配置 Key 的环境连启动都会失败。
            if agent_llm is not None:
                app.state.agent_llm = agent_llm
            elif config.OPENAI_API_KEY:
                app.state.agent_llm = OpenAICompatibleLLM()

            # 多专家平台：default 专家沿用旧目录，其余专家在 agents_dir/<id>/ 下
            store = AgentStore(
                agents_dir or config.AGENTS_DIR,
                upload_dir,
                index_dir,
                agent_log_dir or config.AGENT_LOG_DIR,
                emb,
            )
            app.state.store = store
            if seed_builtin:
                try:
                    ensure_seed_agents(store)
                except Exception as e:  # 播种失败绝不阻塞启动
                    logger.warning("内置专家播种失败：%s", e)
        if not config.ADMIN_TOKEN:
            logger.warning("未设置 ADMIN_TOKEN，写接口对所有人开放")
        yield

    app = FastAPI(title="AI KB QA System", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    max_bytes = max_upload_mb * 1024 * 1024
    limiter = RateLimiter(per_minute=config.RATE_LIMIT_PER_MIN)

    # B3：按专家配置的模型名创建 LLM 实例，带缓存。
    # 测试注入了 agent_llm 而没有 factory 时直接复用注入实例（旧测试不受影响）。
    _llm_cache: dict = {}
    _llm_lock = __import__("threading").Lock()

    def _llm_for(model: str) -> AgentLLM:
        base = getattr(app.state, "agent_llm", None)
        if not model:
            return base
        if agent_llm_factory is None:
            return base
        key = model.strip()
        with _llm_lock:
            if key in _llm_cache:
                return _llm_cache[key]
        instance = agent_llm_factory(key)
        with _llm_lock:
            return _llm_cache.setdefault(key, instance)

    def _require(request: Request, name: str):
        service = getattr(request.app.state, name, None)
        if service is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
        return service

    @app.get("/api/health")
    def health():
        return {"status": "ok", "message": "server running"}

    def _agent_kb(request: Request, agent_id: str):
        """按 agent_id 取该专家的知识库；default 走 app.state.kb（零开销兼容）。

        无 Key 环境 kb 可能是 None：_require 会对上传/问答 503，
        但列表接口允许 None（返回空列表），与旧行为一致。
        """
        if not agent_id or agent_id == DEFAULT_AGENT_ID:
            kb = getattr(request.app.state, "kb", None)
            if kb is None:
                raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
            return kb
        store = getattr(request.app.state, "store", None)
        if store is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
        try:
            return store.kb(agent_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"专家不存在：{agent_id}")

    def _agent_meta(request: Request, agent_id: str) -> dict:
        """取专家定义（persona / greeting 等）；default 无自定义时用内置定义。"""
        store = getattr(request.app.state, "store", None)
        if store is None:
            return {}
        entry = store.get(agent_id)
        return entry or {}

    @app.post("/api/feedback")
    def submit_feedback(req: FeedbackRequest, request: Request):
        """回答反馈：限流但不要求管理员口令；专家不存在 404；写失败仍 200。"""
        limiter.check("feedback:" + client_key(request))
        store = getattr(request.app.state, "store", None)
        if store is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
        if req.agent_id != DEFAULT_AGENT_ID and not store.get(req.agent_id):
            raise HTTPException(status_code=404, detail="专家不存在")
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent_id": req.agent_id,
            "question": req.question,
            "answer": req.answer,
            "rating": req.rating,
            "reason": req.reason,
            "mode": req.mode,
            "grounded_ratio": req.grounded_ratio,
        }
        try:
            log_dir = store.log_dir_of(req.agent_id) if req.agent_id != DEFAULT_AGENT_ID else (
                agent_log_dir or config.AGENT_LOG_DIR)
            os.makedirs(log_dir, exist_ok=True)
            _append_feedback(
                os.path.join(log_dir, "feedback.jsonl"),
                json.dumps(entry, ensure_ascii=False) + "\n",
                int(config.FEEDBACK_MAX_MB * 1024 * 1024),
            )
        except Exception:
            logger.warning("feedback 落盘失败", exc_info=True)
        return {"status": "ok"}

    @app.get("/api/chunks/{chunk_id}")
    def get_chunk(chunk_id: str, request: Request, agent_id: str = DEFAULT_AGENT_ID,
                  neighbors: int = 0):
        """按 chunk_id 返回出处片段原文（含前后相邻片段，供出处弹层展示）。"""
        store = getattr(request.app.state, "store", None)
        if store is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
        try:
            kb = store.kb(agent_id) if agent_id and agent_id != DEFAULT_AGENT_ID else getattr(
                request.app.state, "kb", None)
        except Exception:
            kb = getattr(request.app.state, "kb", None)
        if kb is None:
            raise HTTPException(status_code=503, detail="知识库未就绪")
        doc = kb.get_chunk(chunk_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="片段不存在")
        meta = doc.metadata or {}
        result = {
            "chunk_id": chunk_id,
            "doc_id": meta.get("doc_id"),
            "source": meta.get("source"),
            "page": meta.get("page"),
            "content": doc.page_content,
        }
        window = max(0, min(int(neighbors), 3))
        if window:
            nbs = kb.get_neighbors(chunk_id, window=window)
            result["neighbors"] = [
                {"chunk_id": (n.metadata or {}).get("chunk_id"),
                 "doc_id": (n.metadata or {}).get("doc_id"),
                 "source": (n.metadata or {}).get("source"),
                 "page": (n.metadata or {}).get("page"),
                 "content": n.page_content}
                for n in nbs
            ]
        return {"status": "ok", "chunk": result}

    @app.get("/api/docs")
    def list_docs(request: Request, agent_id: str = DEFAULT_AGENT_ID):
        # 列表接口：服务未就绪时返回空列表，不 503（与旧行为一致）
        if not agent_id or agent_id == DEFAULT_AGENT_ID:
            kb = getattr(request.app.state, "kb", None)
            return {"status": "ok", "docs": kb.list_documents() if kb else []}
        kb = _agent_kb(request, agent_id)
        return {"status": "ok", "docs": kb.list_documents()}

    @app.get("/api/agents")
    def list_agents(request: Request):
        store = getattr(request.app.state, "store", None)
        if store is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
        # B4：给每个专家补文档数（KB 未就绪时置 0，不阻塞列表）
        agents = store.list_agents()
        for a in agents:
            try:
                kb = store.kb(a["agent_id"])
                a["doc_count"] = len(kb.list_documents())
            except Exception:
                a["doc_count"] = 0
        return {"status": "ok", "agents": agents}

    @app.post("/api/agents")
    def create_agent(req: AgentCreateRequest, request: Request, _: None = Depends(require_admin)):
        if getattr(request.app.state, "store", None) is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
        try:
            entry = request.app.state.store.create(
                name=req.name,
                description=req.description,
                persona=req.persona,
                greeting=req.greeting,
                emoji=req.emoji,
                model=req.model,
                agent_id=req.agent_id or None,
                answer_mode=req.answer_mode,
                starter_questions=req.starter_questions,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return {"status": "ok", **entry}

    @app.delete("/api/agents/{agent_id}")
    def delete_agent(agent_id: str, request: Request, _: None = Depends(require_admin)):
        store = getattr(request.app.state, "store", None)
        if store is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
        removed = store.delete(agent_id)
        if removed is None:
            raise HTTPException(status_code=404, detail=f"专家不存在或不可删除：{agent_id}")
        return {"status": "ok", **removed}

    @app.post("/api/upload")
    async def upload_file(
        request: Request,
        file: UploadFile = File(...),
        agent_id: str = DEFAULT_AGENT_ID,
        _: None = Depends(require_admin),
    ):
        kb = _agent_kb(request, agent_id)
        display_name = _safe_display_name(file.filename)
        ext = os.path.splitext(display_name)[1].lower()
        if ext not in config.ALLOWED_EXTENSIONS:
            allowed = "、".join(sorted(config.ALLOWED_EXTENSIONS))
            raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅支持 {allowed}")

        # 落盘文件名由服务端生成，彻底避免路径穿越与同名覆盖
        doc_id = uuid.uuid4().hex
        file_path = os.path.join(upload_dir, doc_id + ext)

        size = 0
        try:
            with open(file_path, "wb") as f:
                while block := await file.read(READ_BLOCK):
                    size += len(block)
                    if size > max_bytes:
                        raise HTTPException(
                            status_code=413, detail=f"文件超过 {max_upload_mb}MB 上限"
                        )
                    f.write(block)
            if size == 0:
                raise HTTPException(status_code=400, detail="文件为空")

            chunks = await run_in_threadpool(load_and_split, file_path, doc_id, display_name)
            await run_in_threadpool(kb.add_document, doc_id, display_name, size, chunks)
        except HTTPException:
            _remove_quietly(file_path)
            raise
        except ValueError as e:
            _remove_quietly(file_path)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            _remove_quietly(file_path)
            raise HTTPException(status_code=500, detail=f"文档处理失败：{e}")

        return {
            "status": "ok",
            "doc_id": doc_id,
            "filename": display_name,
            "size": size,
            "chunks": len(chunks),
            "message": "file uploaded and indexed: " + display_name,
        }

    @app.delete("/api/docs/{doc_id}")
    def delete_doc(
        doc_id: str,
        request: Request,
        agent_id: str = DEFAULT_AGENT_ID,
        _: None = Depends(require_admin),
    ):
        kb = _agent_kb(request, agent_id)
        if not DOC_ID_RE.fullmatch(doc_id):
            raise HTTPException(status_code=400, detail="doc_id 格式不合法")
        removed = kb.delete_document(doc_id)
        if removed is None:
            raise HTTPException(status_code=404, detail="文档不存在")

        # 上传目录里的文件按 doc_id + 扩展名存放，不依赖清单里的文件名
        ext = removed.get("ext") or ""
        _remove_quietly(os.path.join(upload_dir, doc_id + ext))
        return {"status": "ok", "doc_id": doc_id, "filename": removed["filename"]}

    @app.post("/api/ask")
    def ask_question(req: AskRequest, request: Request):
        limiter.check(client_key(request))
        if req.agent_id == DEFAULT_AGENT_ID:
            qa = _require(request, "qa")
        else:
            # 非默认专家：用该专家的知识库 + 同一个固定 RAG 模型新建 QAService。
            # QAService 构造只是拼一次 prompt 模板，开销可忽略。
            qa = QAService(_agent_kb(request, req.agent_id), _require(request, "qa_llm"))
        question = req.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="问题不能为空")
        try:
            result = qa.ask(question)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"问答失败：{e}")
        return {"status": "ok", "question": question, **result}

    @app.post("/api/agent/stream")
    async def agent_stream(req: AgentRequest, request: Request, agent_id: str = ""):
        limiter.check(client_key(request))
        # agent_id 双通道兜底: 查询串优先, body 兜底.
        # 前端曾把 agent_id 只放查询串导致检索串库; Pydantic 的 body 默认值
        # ("default") 是 truthy, 不能用 or 短路合并, 查询串有值必须优先.
        effective_agent_id = (agent_id or "").strip() or req.agent_id or DEFAULT_AGENT_ID
        kb = _agent_kb(request, effective_agent_id)
        question = req.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="问题不能为空")

        # 专家配置：persona / model / 回答模式 / 日志目录
        persona = ""
        model = ""
        mode: str = config.DEFAULT_AGENT_ANSWER_MODE
        log_dir = agent_log_dir
        store = getattr(request.app.state, "store", None)
        if store is not None:
            entry = store.get(effective_agent_id)
            if entry:
                persona = entry.get("persona") or ""
                model = entry.get("model") or ""
                mode = effective_mode(entry)
                if effective_agent_id != DEFAULT_AGENT_ID:
                    log_dir = store.log_dir_of(effective_agent_id)  # B2: 用 effective id

        # 请求级模式覆盖（评测用）
        if req.answer_mode in VALID_MODES:
            mode = req.answer_mode

        # B3: 专家配置了模型时用独立实例（带缓存），否则用默认实例
        llm_impl = _llm_for(model) if model else _require(request, "agent_llm")
        if llm_impl is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)

        # run_agent 是同步生成器，交给 sse 层在后台线程里逐条取，避免阻塞事件循环
        events = run_agent(
            question,
            kb,
            llm_impl,
            max_steps=agent_max_steps,
            log_dir=log_dir,
            enable_decompose=config.QUERY_DECOMPOSE_ENABLED,
            enable_rerank=config.RERANK_ENABLED,
            persona=persona,
            agent_id=effective_agent_id,
            answer_mode=mode,
            history=[h.model_dump() for h in req.history],
            # B8：phase 事件默认关，AGENT_PHASE_EVENTS 开启后前端可展示研究阶段
            emit_phases=os.getenv("AGENT_PHASE_EVENTS", "").strip().lower()
            in ("1", "true", "yes", "on"),
            enable_intent=config.INTENT_ROUTING_ENABLED,
        )
        return StreamingResponse(
            stream_events(events, request.is_disconnected),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    # 前端由 Next.js 独立部署，后端只提供 API，不再托管任何静态资源。
    return app


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


app = create_app()
