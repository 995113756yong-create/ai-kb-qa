"""文档加载、切分与知识库（FAISS 索引 + 文档清单）管理。"""
import json
import logging
import os
import re
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app import config
from app.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    HYBRID_BM25_WEIGHT,
    HYBRID_SEARCH_ENABLED,
    HYBRID_VECTOR_WEIGHT,
    OPENAI_API_BASE,
    OPENAI_API_KEY,
    RRF_K,
)
from app.retrieval import BM25Index, fuse_scores, hybrid_search

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
        # 同上：运行时读 config，避免 from-import 绑定导致无法覆盖
        openai_api_key=config.OPENAI_API_KEY,
        openai_api_base=config.OPENAI_API_BASE,
        check_embedding_ctx_length=False,
        timeout=config.EMBEDDING_TIMEOUT_SECONDS,
        max_retries=config.LLM_MAX_RETRIES,
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


@dataclass
class Hit:
    """retrieve() 的一条结果。

    score 是融合分（相对值，只用于排序）；
    vector_sim 是查询与片段的余弦相似度（绝对值，用于证据门槛），
    与向量是否归一化无关；取不到向量时为 0.0。
    keyword_hit 表示查询里的编号/型号类 token 在片段中原样出现。
    """

    doc: Document
    score: float
    vector_sim: float
    keyword_hit: bool


# ---------- 编号关键词门槛 ----------

_IDENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]*")


def identifier_tokens(query: str) -> List[str]:
    """编号/型号类 token：长度 >= 3 且包含数字，例如 6145、GB1001、X-200。

    FAISS 的语义空间里这类 token 没有语义信息，余弦相似度天然偏低，
    所以它们是绕过余弦门槛的第二通道。
    """
    return [
        t.lower()
        for t in _IDENT_RE.findall(query)
        if len(t) >= 3 and any(c.isdigit() for c in t)
    ]


def has_keyword_hit(tokens: List[str], text: str) -> bool:
    """token 在文本中按词边界原样出现（不区分大小写）。"""
    if not tokens:
        return False
    low = text.lower()
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", low) for t in tokens
    )


class KnowledgeBase:
    """进程内单例：启动时加载一次索引，写入时追加并落盘。"""

    def __init__(self, index_dir: str, embeddings: Embeddings):
        self.index_dir = index_dir
        self.embeddings = embeddings
        self._lock = threading.Lock()
        self._store: Optional[FAISS] = None
        self._docs: List[dict] = []
        # BM25 索引：纯内存，从 FAISS 的 docstore 重建，不额外落盘
        self._bm25 = BM25Index()
        self.hybrid_enabled = HYBRID_SEARCH_ENABLED
        # {docstore_id: faiss_pos} 反查表缓存；删除文档会改变 FAISS 位置编号，
        # 所以每次增删后置 None，用时重建。
        self._pos_by_doc_id: Optional[Dict[str, int]] = None
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

        self._pos_by_doc_id = None
        self._rebuild_bm25()

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
        """先算向量再进锁写入。

        算向量要调外部 Embedding 接口，通常几百毫秒到几秒。如果放在锁里，
        期间所有检索和删除都会被阻塞，一份大 PDF 就足以卡住线上全部问答。
        """
        if not chunks:
            raise ValueError("文档内容为空，无法建立索引")

        texts = [c.page_content for c in chunks]
        ids = [c.metadata["chunk_id"] for c in chunks]
        metadatas = [c.metadata for c in chunks]

        # 锁外完成网络调用
        vectors = self.embeddings.embed_documents(texts)
        if len(vectors) != len(texts):
            raise ValueError("向量数量与片段数量不一致，无法建立索引")

        entry = {
            "doc_id": doc_id,
            "filename": source,
            "ext": os.path.splitext(source)[1].lower(),
            "size": size,
            "chunks": len(chunks),
            "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

        with self._lock:
            # 进锁后重新判断：算向量期间可能有别的上传已经把索创建好了
            created_store = self._store is None
            if created_store:
                self._store = FAISS.from_embeddings(
                    list(zip(texts, vectors)),
                    self.embeddings,
                    metadatas=metadatas,
                    ids=ids,
                )
            else:
                self._store.add_embeddings(list(zip(texts, vectors)), metadatas=metadatas, ids=ids)

            self._docs.append(entry)
            self._pos_by_doc_id = None
            self._rebuild_bm25()
            try:
                self._save()
            except Exception:
                # 落盘失败必须回滚，否则内存里有这份文档、磁盘没有，
                # 接口却返回 500 且上传文件已被删除，重启后文档凭空消失。
                self._docs.pop()
                if created_store:
                    self._store = None
                else:
                    try:
                        self._store.delete(ids)
                    except Exception as e:
                        # 回滚也失败时只能重建索引，避免留下内容缺失的孤儿向量
                        logger.error("回滚新增向量失败（%s），索引将重建", e)
                        self._store = None
                        self._docs = []
                self._drop_index_files()
                raise

    def _rebuild_bm25(self) -> None:
        """从 FAISS 的 docstore 重建 BM25 索引。

        BM25 只依赖原文，不落盘：重启时从向量库的 docstore 直接重建，
        省掉一份持久化数据，也不会出现两份索引不一致的问题。
        """
        if self._store is None:
            self._bm25 = BM25Index()
            return

        docstore = self._store.docstore
        docs: List[Document] = []
        ids: List[str] = []
        for cid, stored in docstore._dict.items():
            if isinstance(stored, Document):
                docs.append(stored)
                ids.append(str(cid))

        self._bm25 = BM25Index()
        self._bm25.build(docs, ids)

    def search(self, query: str, k: int) -> List[Document]:
        """固定 RAG / 评测的检索入口：薄封装，走统一的 retrieve()。"""
        return [h.doc for h in self.retrieve(query, k)]

    def retrieve(self, query: str, k: int, doc_id: Optional[str] = None) -> List[Hit]:
        """统一检索入口：Agent（search_kb）、固定 RAG、评测都走这里。

        返回带绝对余弦相似度（vector_sim）与编号关键词命中标记（keyword_hit）
        的结果，证据门槛基于这两个字段判定，retrieve 本身保持中立只给分数。
        """
        # 查询向量在锁外计算：与 add_document 向量化放锁外的原则一致，
        # Embedding 接口是网络调用，锁内执行会阻塞全部检索。
        q = np.asarray(self.embeddings.embed_query(query), dtype="float32")
        tokens = identifier_tokens(query)

        with self._lock:
            if self._store is None:
                return []

            fetch = max(k * 2, k + 2)  # 与旧 search() 保持一致，bench 结果不变

            # ---- 两路召回 ----
            if doc_id:
                total = int(getattr(self._store.index, "ntotal", 0) or 0)
                vector_hits = self._store.similarity_search_with_score(
                    query, k=fetch, filter={"doc_id": doc_id},
                    fetch_k=max(total, fetch, 1),
                )
                if self.hybrid_enabled:
                    raw_bm25 = self._bm25.search(query, k=self._bm25.size)
                    bm25_hits = [
                        (d, s) for d, s in raw_bm25
                        if (d.metadata or {}).get("doc_id") == doc_id
                    ][:fetch]
                else:
                    bm25_hits = []
            else:
                vector_hits = self._store.similarity_search_with_score(query, k=fetch)
                bm25_hits = self._bm25.search(query, k=fetch) if self.hybrid_enabled else []

            # ---- 排序融合 ----
            if self.hybrid_enabled and bm25_hits:
                fused = fuse_scores(
                    vector_hits, bm25_hits,
                    vector_weight=HYBRID_VECTOR_WEIGHT,
                    bm25_weight=HYBRID_BM25_WEIGHT,
                    limit=k,
                )
                def _key_of(doc: Document) -> str:
                    meta = doc.metadata or {}
                    return str(meta.get("chunk_id") or f"{meta.get('doc_id')}:{meta.get('chunk_index')}")
                by_key: Dict[str, Tuple[Document, float]] = {}
                for doc, score in list(vector_hits) + list(bm25_hits):
                    by_key.setdefault(_key_of(doc), (doc, score))
                chosen = [(by_key[key][0], score) for key, score in fused if key in by_key]
            else:
                # 非混合或 BM25 无结果：按向量距离升序，score = 1 - 归一化距离
                ordered = sorted(vector_hits, key=lambda ds: ds[1])
                if not ordered:
                    return []
                dists = [d for _, d in ordered]
                lo, hi = min(dists), max(dists)
                span = (hi - lo) or 1.0
                chosen = [(doc, 1.0 - (dist - lo) / span) for doc, dist in ordered[:k]]

            if not chosen:
                return []

            # ---- 对最终入选结果计算绝对余弦与关键词命中 ----
            out: List[Hit] = []
            for doc, score in chosen[:k]:
                v = self._vector_of(str((doc.metadata or {}).get("chunk_id") or ""))
                if v is not None:
                    denom = float(np.linalg.norm(q)) * float(np.linalg.norm(v)) + 1e-12
                    sim = float(np.dot(q, v) / denom)
                else:
                    sim = 0.0
                out.append(
                    Hit(
                        doc=doc,
                        score=float(score),
                        vector_sim=sim,
                        keyword_hit=has_keyword_hit(tokens, doc.page_content),
                    )
                )
            return out

    def _vector_of(self, chunk_id: str) -> Optional[np.ndarray]:
        """从 FAISS 取回片段向量。在锁内调用。

        反查表 {docstore_id: faiss_pos} 由 index_to_docstore_id 反转得到，
        增删文档后置 None 重建（删除会重编号 FAISS 位置）。
        取不到向量（旧格式索引 id 不是 chunk_id）返回 None。
        """
        if self._store is None:
            return None
        if not chunk_id:
            return None
        if self._pos_by_doc_id is None:
            self._pos_by_doc_id = {
                str(ds_id): pos
                for pos, ds_id in self._store.index_to_docstore_id.items()
            }
        pos = self._pos_by_doc_id.get(chunk_id)
        if pos is None:
            return None
        try:
            return np.asarray(self._store.index.reconstruct(int(pos)), dtype="float32")
        except Exception:
            return None

    def search_with_scores(
        self, query: str, k: int, doc_id: Optional[str] = None
    ) -> List[Tuple[Document, float]]:
        """已废弃：Agent 已改用 retrieve()，仅为兼容旧测试保留。

        返回的分数是 FAISS 的 L2 距离平方（越小越近），不是相似度。
        """
        with self._lock:
            if self._store is None:
                return []
            if doc_id:
                # FAISS 的 filter 是「先取 fetch_k 条再筛」，不是按条件检索。
                # 用 k*4 这种小倍数时，只要另一份文档够大就会把候选占满，
                # 目标文档可能一条都筛不出来。必须把候选放到全量才不会漏。
                total = int(getattr(self._store.index, "ntotal", 0) or 0)
                return self._store.similarity_search_with_score(
                    query,
                    k=k,
                    filter={"doc_id": doc_id},
                    fetch_k=max(total, k, 1),
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

            # 清单记录的片段数可能与索引不一致（历史数据、写入中断等），
            # FAISS.delete 遇到不存在的 ID 会整体抛错，这里先取交集。
            expected = [chunk_id_of(doc_id, i) for i in range(target["chunks"])]
            existing = set(self._store.index_to_docstore_id.values())
            ids = [chunk_id for chunk_id in expected if chunk_id in existing]
            if ids:
                self._store.delete(ids)
            else:
                logger.warning(
                    "文档 %s 的片段在索引中均不存在（清单记为 %s 个），只清理清单",
                    doc_id,
                    target["chunks"],
                )
            self._docs = [d for d in self._docs if d["doc_id"] != doc_id]
            self._pos_by_doc_id = None

            if getattr(self._store.index, "ntotal", 0):
                # 删除后必须重建 BM25，否则已删片段还能被关键词路召回，
                # 出现「向量库没有、BM25 还能搜到」的不一致。
                self._rebuild_bm25()
                self._save()
            else:
                # 索引空了就彻底清掉，下次上传重建，避免残留空索引
                self._store = None
                self._pos_by_doc_id = None
                self._bm25 = BM25Index()
                self._drop_index_files()
                self._write_manifest()
            return target

    def list_documents(self) -> List[dict]:
        with self._lock:
            return list(self._docs)
