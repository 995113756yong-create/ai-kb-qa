import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app import config
from app.document import KnowledgeBase, get_embeddings, load_and_split
from app.qa import QAService, get_llm

READ_BLOCK = 1024 * 1024
MISSING_KEY_MSG = "服务未配置 OPENAI_API_KEY，暂时无法上传和问答"

logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
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
) -> FastAPI:
    """应用工厂：生产环境用默认参数；测试时注入假的 embeddings / llm 和临时目录。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        os.makedirs(upload_dir, exist_ok=True)
        app.state.kb = app.state.qa = None
        if embeddings is None and not config.OPENAI_API_KEY:
            # 不阻止启动：健康检查和前端照常可用，上传/问答返回 503
            logger.warning(MISSING_KEY_MSG)
        else:
            kb = KnowledgeBase(index_dir, embeddings or get_embeddings())
            app.state.kb = kb
            app.state.qa = QAService(kb, llm or get_llm())
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

    # 前端托管：StaticFiles 会校验路径必须位于目录内，替代原来的手写兜底路由。
    # 必须最后挂载，否则会吞掉 /api 路由。
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
    return app


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


app = create_app()
