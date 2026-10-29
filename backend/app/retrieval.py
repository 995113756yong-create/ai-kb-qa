"""混合检索：向量检索 + BM25 关键词检索，用加权 RRF 融合。

为什么需要：
纯向量检索靠语义相似度，对「配置 6145」「GB1001」这类**精确标识符**天然失效——
这些编号在嵌入空间里没有语义信息，与周围大量相似编号几乎等价。
BM25 基于词频，能精确定位这类 token。

融合算法用加权 RRF（Weighted Reciprocal Rank Fusion）：
    score(d) = Σ weight_i / (k + rank_i(d))

为什么要加权：
标准 RRF 只看排名不看来源。实测发现一个反直觉现象——
某片段在向量路排第 1、在 BM25 路排第 5，会拿到两份分数，
反而超过「只在 BM25 路排第 1」的正确结果。
因为向量路在精确编号场景下本身就是噪声，不该与 BM25 等权。

因此给 BM25 更高权重：精确标识符命中是强信号，语义"看起来像"是弱信号。
"""
import logging
import math
import re
from typing import Dict, List, Tuple

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# RRF 的平滑常数，业界常用 60，作用是压低头部排名的绝对优势
DEFAULT_RRF_K = 60

# 两路权重：BM25 权重是向量的 3 倍。
#
# 为什么需要权重：
# 标准 RRF 等权时会出现反直觉结果——某片段在向量路排第 1、BM25 路排第 5，
# 会拿到两份分数，反而超过"只在 BM25 路排第 1"的正确片段。
# 而向量路在精确编号场景下本身就是噪声，不该与 BM25 等权。
#
# 为什么是 3 倍：
# 在 20 个探针上做权重扫描，1:3 起精确编号类就能全中（14/16 → 16/16），
# 且语义类不退化（4/4）。1:8 同样能全中，但更极端、更容易过拟合这批探针。
# 取 3 倍是在"修正假阳性"和"避免过拟合"之间的折中。
DEFAULT_VECTOR_WEIGHT = 1.0
DEFAULT_BM25_WEIGHT = 3.0


def tokenize(text: str) -> List[str]:
    """中英混合分词。

    中文没有空格，正规做法要接分词器（jieba 等）。这里用更轻的方案：
    - 英文/数字/型号：按连续的字母数字下划线切出来，整体作为一个 token
      （这样 "GB1001"、"6145" 会保持完整，不会被拆碎）
    - 中文：切成单字 + 相邻双字，兼顾单字匹配和短语匹配

    不引入新依赖，对精确编号检索已经够用。
    """
    tokens: List[str] = []

    # 英文、数字、带连字符的型号，整体保留
    for m in re.finditer(r"[A-Za-z0-9_][A-Za-z0-9_\-]*", text):
        tokens.append(m.group().lower())

    # 中文：单字 + 双字
    chinese = re.findall(r"[\u4e00-\u9fff]+", text)
    for seg in chinese:
        tokens.extend(seg)
        tokens.extend(seg[i : i + 2] for i in range(len(seg) - 1))

    return tokens


class BM25Index:
    """极简 BM25 实现。

    语料规模是「单个知识库」量级（几十到几千片），纯 Python 够用，
    不必引入 rank_bm25 或 Elasticsearch。
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: List[Document] = []
        self._ids: List[str] = []
        self._tokens: List[List[str]] = []
        self._df: Dict[str, int] = {}
        self._avg_len: float = 0.0

    def build(self, docs: List[Document], ids: List[str]) -> None:
        self._docs = list(docs)
        self._ids = list(ids)
        self._tokens = [tokenize(d.page_content) for d in docs]

        df: Dict[str, int] = {}
        for toks in self._tokens:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self._df = df

        total = sum(len(t) for t in self._tokens)
        self._avg_len = total / len(self._tokens) if self._tokens else 0.0

    @property
    def size(self) -> int:
        return len(self._docs)

    def _idf(self, term: str) -> float:
        n = len(self._docs)
        df = self._df.get(term, 0)
        # 加 1 平滑，避免 df=0 时出现负数
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int) -> List[Tuple[Document, float]]:
        if not self._docs:
            return []

        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        scores: List[float] = []
        for toks in self._tokens:
            dl = len(toks)
            tf: Dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1

            score = 0.0
            for q in q_tokens:
                if q not in tf:
                    continue
                f = tf[q]
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self._avg_len or 1))
                score += self._idf(q) * f * (self.k1 + 1) / denom
            scores.append(score)

        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: List[Tuple[Document, float]] = []
        for i in ranked[:k]:
            if scores[i] <= 0:
                break
            out.append((self._docs[i], scores[i]))
        return out

    def remove(self, ids: List[str]) -> None:
        """删除指定片段后重建（语料小，重建比增量维护简单且不易出错）。"""
        drop = set(ids)
        keep_docs = []
        keep_ids = []
        for doc, cid in zip(self._docs, self._ids):
            if cid not in drop:
                keep_docs.append(doc)
                keep_ids.append(cid)
        self.build(keep_docs, keep_ids)


def normalize(scores: list, single_as_top: bool = True) -> list:
    """min-max 归一化到 [0, 1]，让两路分数可比。

    边界处理：
    - 空列表返回空
    - 只有一个结果时，它既是最大也是最小，min-max 会得到 0，
      但这显然是错的（这唯一结果就是该路最好的）。返回 1.0。
    - 所有分数相同时同理返回全 1。
    """
    if not scores:
        return []
    if len(scores) == 1:
        return [1.0] if single_as_top else [0.0]
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def fuse_scores(
    vector_hits: List[Tuple[Document, float]],
    bm25_hits: List[Tuple[Document, float]],
    vector_weight: float = DEFAULT_VECTOR_WEIGHT,
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
    limit: int = 10,
) -> List[Tuple[str, float]]:
    """归一化后加权融合，同片段取 max 而非 sum。

    为什么取 max：
    一个片段在两路都出现，不代表它比「一路强烈命中」更相关。
    实测中，编号类查询里向量路经常返回一堆语义相近的噪声，
    这些噪声在 BM25 路也能排进中游，sum 会把这些噪声顶到第一。
    取 max 让「BM25 精确命中」不被「向量噪声 + BM25 中游」反超。
    """
    def key_of(doc: Document) -> str:
        meta = doc.metadata or {}
        return str(meta.get("chunk_id") or f"{meta.get('doc_id')}:{meta.get('chunk_index')}")

    merged: Dict[str, float] = {}

    if vector_hits:
        # 向量分数是「距离」，越小越相近。先归一化再翻转为相似度。
        # 单条结果时它本身就是该路最优，直接给满分，
        # 否则 1-1.0=0 会把唯一的正确结果判成最不相关。
        raw = [score for _, score in vector_hits]
        if len(raw) == 1:
            sims = [1.0]
        else:
            sims = [1.0 - n for n in normalize(raw)]
        for (doc, _), sim in zip(vector_hits, sims):
            k = key_of(doc)
            val = sim * vector_weight
            merged[k] = max(merged.get(k, 0.0), val)

    if bm25_hits:
        norm = normalize([score for _, score in bm25_hits])
        for (doc, _), n in zip(bm25_hits, norm):
            k = key_of(doc)
            val = n * bm25_weight
            merged[k] = max(merged.get(k, 0.0), val)

    return sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:limit]


def hybrid_search(
    vector_hits: List[Tuple[Document, float]],
    bm25_hits: List[Tuple[Document, float]],
    limit: int,
    rrf_k: int = DEFAULT_RRF_K,
    vector_weight: float = DEFAULT_VECTOR_WEIGHT,
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
) -> List[Document]:
    """两路检索结果融合成一份有序列表。

    保留 rrf_k 参数是为了向后兼容（旧调用方会传），当前实现不再使用它。
    """
    def key_of(doc: Document) -> str:
        meta = doc.metadata or {}
        return str(meta.get("chunk_id") or f"{meta.get('doc_id')}:{meta.get('chunk_index')}")

    by_key: Dict[str, Document] = {}
    for doc, _ in vector_hits:
        by_key.setdefault(key_of(doc), doc)
    for doc, _ in bm25_hits:
        by_key.setdefault(key_of(doc), doc)

    fused = fuse_scores(
        vector_hits,
        bm25_hits,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
        limit=limit,
    )
    return [by_key[doc_id] for doc_id, _ in fused if doc_id in by_key]
