"""文档加载、切分与知识库（FAISS 索引 + 文档清单）管理。"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import List, Optional

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    OPENAI_API_BASE,
    OPENAI_API_KEY,
)

MANIFEST_FILE = "docs.json"


def get_embeddings() -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
        check_embedding_ctx_length=False,
    )


def load_and_split(file_path: str, doc_id: str, source: str) -> List[Document]:
    """加载文件并切分，每个片段的 metadata 记录 doc_id / source / page / chunk_index。"""
    if file_path.lower().endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    else:
        loader = TextLoader(file_path, encoding="utf-8")
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(pages)

    for i, chunk in enumerate(chunks):
        page = chunk.metadata.get("page")
        chunk.metadata = {
            "doc_id": doc_id,
            "source": source,
            # PyPDFLoader 的页码从 0 开始，这里转成人类习惯的 1 开始；文本文件没有页码
            "page": page + 1 if isinstance(page, int) else None,
            "chunk_index": i,
        }
    return chunks


class KnowledgeBase:
    """进程内单例：启动时加载一次索引，写入时追加并落盘。"""

    def __init__(self, index_dir: str, embeddings: Embeddings):
        self.index_dir = index_dir
        self.embeddings = embeddings
        self._lock = threading.Lock()
        self._store: Optional[FAISS] = None
        self._docs: List[dict] = []
        self._load()

    # ---------- 持久化 ----------
    def _manifest_path(self) -> str:
        return os.path.join(self.index_dir, MANIFEST_FILE)

    def _load(self) -> None:
        if os.path.exists(os.path.join(self.index_dir, "index.faiss")):
            # 索引文件只由本服务写入；路由穿越已修复，外部无法替换该文件
            self._store = FAISS.load_local(
                self.index_dir,
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
        if os.path.exists(self._manifest_path()):
            with open(self._manifest_path(), encoding="utf-8") as f:
                self._docs = json.load(f)

    def _save(self) -> None:
        os.makedirs(self.index_dir, exist_ok=True)
        self._store.save_local(self.index_dir)
        tmp = self._manifest_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._docs, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._manifest_path())

    # ---------- 读写 ----------
    @property
    def is_empty(self) -> bool:
        return self._store is None

    def add_document(self, doc_id: str, source: str, size: int, chunks: List[Document]) -> None:
        if not chunks:
            raise ValueError("文档内容为空，无法建立索引")
        with self._lock:
            if self._store is None:
                self._store = FAISS.from_documents(chunks, self.embeddings)
            else:
                self._store.add_documents(chunks)
            self._docs.append(
                {
                    "doc_id": doc_id,
                    "filename": source,
                    "size": size,
                    "chunks": len(chunks),
                    "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            self._save()

    def search(self, query: str, k: int) -> List[Document]:
        with self._lock:
            if self._store is None:
                return []
            return self._store.similarity_search(query, k=k)

    def list_documents(self) -> List[dict]:
        with self._lock:
            return list(self._docs)
