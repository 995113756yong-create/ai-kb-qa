"""文档加载、切分与知识库（FAISS 索引 + 文档清单）管理。"""
import json
import logging
import os
import shutil
import threading
from datetime import datetime, timezone
from typing import List, Optional, Tuple

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
MANIFEST_VERSION = 2
INDEX_FILE = "index.faiss"
INDEX_PKL = "index.pkl"

logger = logging.getLogger(__name__)


def chunk_id_of(doc_id: str, chunk_index: int) -> str:
    """片段 ID：文档 ID + 片段序号，全局唯一且可逆推。"""
    return f"{doc_id}:{chunk_index}"


def get_embeddings() -> Embeddings:
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
        check_embedding_ctx_length=False,
    )


def load_and_split(file_path: str, doc_id: str, source: str) -> List[Document]:
    """加载文件并切分，每个片段的 metadata 记录 doc_id / source / page / chunk_index / chunk_id。"""
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
            "chunk_id": chunk_id_of(doc_id, i),
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

    def _index_path(self) -> str:
        return os.path.join(self.index_dir, INDEX_FILE)

    def _write_manifest(self) -> None:
        os.makedirs(self.index_dir, exist_ok=True)
        tmp = self._manifest_path() + ".tmp"
        payload = {"version": MANIFEST_VERSION, "docs": self._docs}
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._manifest_path())

    def _save(self) -> None:
        os.makedirs(self.index_dir, exist_ok=True)
        self._store.save_local(self.index_dir)
        self._write_manifest()

    def _load(self) -> None:
        if not os.path.exists(self._index_path()):
            return
        if not self._manifest_is_current():
            # 旧版清单（无 version 字段）或清单缺失：不尝试迁移，整体备份后以空库启动
            self._backup_legacy_index()
            return

        # 索引文件只由本服务写入；路由穿越已修复，外部无法替换该文件
        self._store = FAISS.load_local(
            self.index_dir,
            self.embeddings,
            allow_dangerous_deserialization=True,
        )
        with open(self._manifest_path(), encoding="utf-8") as f:
            self._docs = json.load(f).get("docs", [])

    def _manifest_is_current(self) -> bool:
        path = self._manifest_path()
        if not os.path.exists(path):
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        return isinstance(data, dict) and data.get("version") == MANIFEST_VERSION

    def _backup_legacy_index(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = f"{self.index_dir.rstrip(os.sep)}.legacy-{stamp}"
        try:
            shutil.move(self.index_dir, backup)
            logger.warning("检测到旧版索引，已备份到 %s，以空知识库启动", backup)
        except OSError as e:
            # 备份失败也不能把旧索引当成正常库加载
            logger.warning("旧版索引备份失败（%s），按空知识库启动", e)
        self._store = None
        self._docs = []

    def _drop_index_files(self) -> None:
        for name in (INDEX_FILE, INDEX_PKL):
            try:
                os.remove(os.path.join(self.index_dir, name))
            except OSError:
                pass

    # ---------- 读写 ----------
    @property
    def is_empty(self) -> bool:
        return self._store is None

    def add_document(self, doc_id: str, source: str, size: int, chunks: List[Document]) -> None:
        if not chunks:
            raise ValueError("文档内容为空，无法建立索引")
        ids = [c.metadata["chunk_id"] for c in chunks]
        with self._lock:
            if self._store is None:
                self._store = FAISS.from_documents(chunks, self.embeddings, ids=ids)
            else:
                self._store.add_documents(chunks, ids=ids)
            self._docs.append(
                {
                    "doc_id": doc_id,
                    "filename": source,
                    "ext": os.path.splitext(source)[1].lower(),
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

    def search_with_scores(
        self, query: str, k: int, doc_id: Optional[str] = None
    ) -> List[Tuple[Document, float]]:
        """带相关度分数的检索；传 doc_id 时只在该文档内检索。"""
        with self._lock:
            if self._store is None:
                return []
            if doc_id:
                # 过滤后可用候选会变少，先多取一些再过滤，避免结果不足
                return self._store.similarity_search_with_score(
                    query, k=k, filter={"doc_id": doc_id}, fetch_k=k * 4
                )
            return self._store.similarity_search_with_score(query, k=k)

    def get_chunk(self, chunk_id: str) -> Optional[Document]:
        with self._lock:
            if self._store is None:
                return None
            try:
                found = self._store.docstore.search(chunk_id)
            except KeyError:
                return None
            # InMemoryDocstore 找不到时不抛异常，而是返回一段提示字符串
            return found if isinstance(found, Document) else None

    def get_neighbors(self, chunk_id: str, window: int = 1) -> List[Document]:
        """返回同一文档中 chunk_index ± window 范围内存在的片段，按顺序排列（含自身）。"""
        target = self.get_chunk(chunk_id)
        if target is None:
            return []
        doc_id = target.metadata.get("doc_id")
        index = target.metadata.get("chunk_index")
        if doc_id is None or index is None:
            return [target]

        neighbors: List[Document] = []
        for i in range(index - window, index + window + 1):
            if i < 0:
                continue
            doc = self.get_chunk(chunk_id_of(doc_id, i))
            if doc is not None:
                neighbors.append(doc)
        return neighbors

    def delete_document(self, doc_id: str) -> Optional[dict]:
        """按清单记录的片段数拼出全部 ID 后一次性删除，并在索引清空时清理文件。"""
        with self._lock:
            if self._store is None:
                return None
            target = next((d for d in self._docs if d["doc_id"] == doc_id), None)
            if target is None:
                return None

            ids = [chunk_id_of(doc_id, i) for i in range(target["chunks"])]
            self._store.delete(ids)
            self._docs = [d for d in self._docs if d["doc_id"] != doc_id]

            if getattr(self._store.index, "ntotal", 0):
                self._save()
            else:
                # 索引空了就彻底清掉，下次上传重建，避免残留空索引
                self._store = None
                self._drop_index_files()
                self._write_manifest()
            return target

    def list_documents(self) -> List[dict]:
        with self._lock:
            return list(self._docs)
