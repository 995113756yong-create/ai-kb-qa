import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app import config
from app.agent.llm import AgentLLM, OpenAICompatibleLLM
from app.agent.runner import run_agent
from app.agent.sse import SSE_HEADERS, stream_events
from app.document import KnowledgeBase, get_embeddings, load_and_split
from app.qa import QAService, get_llm

READ_BLOCK = 1024 * 1024
DOC_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MISSING_KEY_MSG = "服务未配置 OPENAI_API_KEY，暂时无法上传和问答"

logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class AgentRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


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
) -> FastAPI:
    """应用工厂：生产环境用默认参数；测试时注入假的 embeddings / llm 和临时目录。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        os.makedirs(upload_dir, exist_ok=True)
        app.state.kb = app.state.qa = app.state.agent_llm = None
        if embeddings is None and not config.OPENAI_API_KEY:
            # 不阻止启动：健康检查照常可用，上传/问答返回 503
            logger.warning(MISSING_KEY_MSG)
        else:
            kb = KnowledgeBase(index_dir, embeddings or get_embeddings())
            app.state.kb = kb
            app.state.qa = QAService(kb, llm or get_llm())
            # Agent 用独立模型（需要稳定的 tools 调用能力），与固定 RAG 分开配置
            app.state.agent_llm = agent_llm or OpenAICompatibleLLM()
        yield

    app = FastAPI(title="AI KB QA System", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    max_bytes = max_upload_mb * 1024 * 1024

    def _require(request: Request, name: str):
        service = getattr(request.app.state, name, None)
        if service is None:
            raise HTTPException(status_code=503, detail=MISSING_KEY_MSG)
        return service

    @app.get("/api/health")
    def health():
        return {"status": "ok", "message": "server running"}

    @app.get("/api/docs")
    def list_docs(request: Request):
        kb = request.app.state.kb
        return {"status": "ok", "docs": kb.list_documents() if kb else []}

    @app.post("/api/upload")
    async def upload_file(request: Request, file: UploadFile = File(...)):
        kb = _require(request, "kb")
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
    def delete_doc(doc_id: str, request: Request):
        kb = _require(request, "kb")
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
        qa = _require(request, "qa")
        question = req.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="问题不能为空")
        try:
            result = qa.ask(question)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"问答失败：{e}")
        return {"status": "ok", "question": question, **result}

    @app.post("/api/agent/stream")
    async def agent_stream(req: AgentRequest, request: Request):
        kb = _require(request, "kb")
        llm_impl = _require(request, "agent_llm")
        question = req.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="问题不能为空")

        # run_agent 是同步生成器，交给 sse 层在后台线程里逐条取，避免阻塞事件循环
        events = run_agent(
            question,
            kb,
            llm_impl,
            max_steps=agent_max_steps,
            log_dir=agent_log_dir,
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
