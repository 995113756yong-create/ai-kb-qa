"""混合检索的单元测试：分词、BM25、RRF 融合、KnowledgeBase 集成。"""
import pytest
from langchain_core.documents import Document

from app.retrieval import (
    DEFAULT_BM25_WEIGHT,
    DEFAULT_VECTOR_WEIGHT,
    BM25Index,
    fuse_scores,
    hybrid_search,
    normalize,
    tokenize,
)


# ---------- 分词 ----------


def test_tokenize_keeps_identifiers_whole():
    """型号、编号必须保持完整，不能被拆碎，否则 BM25 无法精确命中。"""
    tokens = tokenize("配置 6145 和 GB1001 的容量")

    assert "6145" in tokens
    assert "gb1001" in tokens
    # 不能被拆成 "614" "5" 这种
    assert "614" not in tokens


def test_tokenize_chinese_single_and_bigram():
    tokens = tokenize("推送任务")

    assert "推" in tokens  # 单字
    assert "推送" in tokens  # 双字
    assert "任务" in tokens


def test_tokenize_handles_hyphen_model():
    tokens = tokenize("型号 GB-1001 支持")

    assert "gb-1001" in tokens


def test_tokenize_empty():
    assert tokenize("") == []
    assert tokenize("   ") == []


# ---------- BM25 ----------


def _docs(texts):
    return [
        Document(page_content=t, metadata={"doc_id": f"d{i}", "chunk_index": 0, "chunk_id": f"d{i}:0"})
        for i, t in enumerate(texts)
    ]


def test_bm25_finds_exact_identifier():
    """BM25 的核心价值：精确编号必须排第一。"""
    docs = _docs([
        "配置 6001 是常规任务，每天 1 点执行。",
        "配置 6145 是产品A 的默认推送，负责人 zhangsan。",
        "配置 6002 是常规任务，每天 2 点执行。",
    ])
    idx = BM25Index()
    idx.build(docs, [d.metadata["chunk_id"] for d in docs])

    hits = idx.search("配置 6145", k=3)

    assert hits, "应该能检索到结果"
    assert "6145" in hits[0][0].page_content


def test_bm25_no_match_returns_empty():
    docs = _docs(["苹果是一种水果", "火星是一颗行星"])
    idx = BM25Index()
    idx.build(docs, [d.metadata["chunk_id"] for d in docs])

    assert idx.search("量子纠缠", k=3) == []


def test_bm25_empty_index():
    idx = BM25Index()
    assert idx.size == 0
    assert idx.search("任意", k=3) == []


def test_bm25_remove_rebuilds():
    docs = _docs(["配置 6145 是产品A", "配置 6146 是产品B"])
    idx = BM25Index()
    idx.build(docs, [d.metadata["chunk_id"] for d in docs])

    idx.remove(["d0:0"])

    assert idx.size == 1
    assert all("6145" not in d.page_content for d, _ in idx.search("配置 6145", k=5))


# ---------- 归一化与融合 ----------


def test_normalize_to_unit_range():
    out = normalize([1.0, 3.0, 5.0])

    assert out[0] == 0.0 and out[-1] == 1.0
    assert all(0.0 <= x <= 1.0 for x in out)


def test_normalize_flat_scores():
    """所有分数相同时归一化成全 1，不能除零。"""
    assert normalize([2.0, 2.0, 2.0]) == [1.0, 1.0, 1.0]


def test_normalize_empty():
    assert normalize([]) == []


def test_fuse_takes_max_not_sum():
    """核心语义：同一片段在两路都出现，取 max 而不是相加。

    「两路都中等相关」不应超过「一路强烈命中」。
    """
    noise = Document(page_content="噪声", metadata={"chunk_id": "noise"})
    target = Document(page_content="目标", metadata={"chunk_id": "target"})

    # 噪声：向量路很强（距离小），BM25 也出现但较弱
    # 目标：只出现在 BM25 且最强
    vector_hits = [(noise, 0.1)]
    bm25_hits = [(target, 10.0), (noise, 1.0)]

    fused = fuse_scores(vector_hits, bm25_hits, limit=2)

    assert fused[0][0] == "target", "BM25 的强烈命中不能被向量噪声反超"


def test_fuse_weights_affect_ranking():
    a = Document(page_content="a", metadata={"chunk_id": "a"})
    b = Document(page_content="b", metadata={"chunk_id": "b"})

    vector_hits = [(a, 0.1)]
    bm25_hits = [(b, 10.0)]

    # 向量权重远高于 BM25 时，a 应领先
    fused = fuse_scores(vector_hits, bm25_hits, vector_weight=10.0, bm25_weight=1.0, limit=2)
    assert fused[0][0] == "a"

    # 反过来
    fused = fuse_scores(vector_hits, bm25_hits, vector_weight=1.0, bm25_weight=10.0, limit=2)
    assert fused[0][0] == "b"


def test_fuse_respects_limit():
    docs = [Document(page_content=str(i), metadata={"chunk_id": f"d{i}"}) for i in range(5)]
    fused = fuse_scores([(d, float(i)) for i, d in enumerate(docs)], [], limit=2)

    assert len(fused) == 2


def test_default_weights_are_bm25_heavier():
    """默认配置里 BM25 权重必须高于向量，这是修掉假阳性的关键。"""
    assert DEFAULT_BM25_WEIGHT > DEFAULT_VECTOR_WEIGHT


# ---------- hybrid_search ----------


def test_hybrid_prefers_exact_match_over_semantic_noise():
    """混合检索要解决的核心问题。

    向量路返回 5 条语义相近但不是目标的噪声（距离都很小），
    BM25 路第一条才是真正的目标。融合后目标必须排第一。
    """
    def make(idx, text):
        return Document(
            page_content=text,
            metadata={"doc_id": "d", "chunk_index": idx, "chunk_id": f"d:{idx}"},
        )

    noises = [make(i, f"配置 60{i:02d} 是常规任务") for i in range(1, 5)]
    target = make(9, "配置 6145 是产品A 的默认推送")

    # 向量路：全是噪声，距离很小（相似度高）
    vector_hits = [(n, 0.10 + i * 0.01) for i, n in enumerate(noises)]
    # BM25 路：目标最强
    bm25_hits = [(target, 8.0), (noises[0], 5.0)]

    docs = hybrid_search(vector_hits, bm25_hits, limit=3)

    assert docs[0].metadata["chunk_id"] == "d:9", "BM25 的精确命中应该排第一"


def test_hybrid_dedupes_same_chunk():
    """同一片段在两路都出现时，融合结果里只能有一条。"""
    doc = Document(page_content="x", metadata={"doc_id": "d", "chunk_index": 0, "chunk_id": "d:0"})

    docs = hybrid_search([(doc, 0.9)], [(doc, 1.0)], limit=5)

    assert len(docs) == 1


def test_hybrid_handles_empty_vector_route():
    target = Document(page_content="6145", metadata={"chunk_id": "d:0"})

    docs = hybrid_search([], [(target, 1.0)], limit=5)

    assert len(docs) == 1 and docs[0] is target


def test_hybrid_handles_empty_bm25_route():
    target = Document(page_content="语义内容", metadata={"chunk_id": "d:0"})

    docs = hybrid_search([(target, 0.9)], [], limit=5)

    assert len(docs) == 1


def test_hybrid_both_empty():
    assert hybrid_search([], [], limit=5) == []


# ---------- KnowledgeBase 集成 ----------


def test_kb_hybrid_toggle(tmp_path, embeddings):
    """关掉混合模式时要退回纯向量，行为可预期。"""
    from app.document import KnowledgeBase, load_and_split

    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    p = tmp_path / "a.txt"
    p.write_text("配置 6145 是产品A 的默认推送。" * 20, encoding="utf-8")
    kb.add_document("d1", "a.txt", 100, load_and_split(str(p), "d1", "a.txt"))

    kb.hybrid_enabled = True
    assert kb.search("配置 6145", k=1)

    kb.hybrid_enabled = False
    assert kb.search("配置 6145", k=1)


def test_kb_bm25_rebuilt_after_add(tmp_path, embeddings):
    """新增文档后 BM25 必须包含新内容。"""
    from app.document import KnowledgeBase, load_and_split

    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)

    p1 = tmp_path / "a.txt"
    p1.write_text("苹果是一种水果。", encoding="utf-8")
    kb.add_document("d1", "a.txt", 10, load_and_split(str(p1), "d1", "a.txt"))
    assert all("GB9999" not in d.page_content for d, _ in kb._bm25.search("GB9999", k=5))

    p2 = tmp_path / "b.txt"
    p2.write_text("GB9999 是特殊型号。", encoding="utf-8")
    kb.add_document("d2", "b.txt", 10, load_and_split(str(p2), "d2", "b.txt"))

    hits = kb._bm25.search("GB9999", k=5)
    assert any("GB9999" in d.page_content for d, _ in hits)


def test_kb_bm25_rebuilt_after_delete(tmp_path, embeddings):
    """删除文档后 BM25 不能还留着已删内容。

    这是修复过的 bug：删除只更新了 FAISS，BM25 仍能召回已删片段，
    造成「向量库没有、关键词路还能搜到」的不一致。
    """
    from app.document import KnowledgeBase, load_and_split

    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    p1 = tmp_path / "a.txt"
    p1.write_text("GB8888 是待删除型号。", encoding="utf-8")
    kb.add_document("d1", "a.txt", 10, load_and_split(str(p1), "d1", "a.txt"))
    p2 = tmp_path / "b.txt"
    p2.write_text("GB7777 是保留型号。", encoding="utf-8")
    kb.add_document("d2", "b.txt", 10, load_and_split(str(p2), "d2", "b.txt"))

    assert any("GB8888" in d.page_content for d, _ in kb._bm25.search("GB8888", k=5))

    kb.delete_document("d1")

    assert all("GB8888" not in d.page_content for d, _ in kb._bm25.search("GB8888", k=5))
    # 保留的要还在
    assert any("GB7777" in d.page_content for d, _ in kb._bm25.search("GB7777", k=5))


def test_kb_bm25_cleared_when_index_empty(tmp_path, embeddings):
    """删光所有文档后 BM25 也要清空。"""
    from app.document import KnowledgeBase, load_and_split

    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    p = tmp_path / "a.txt"
    p.write_text("唯一的内容。", encoding="utf-8")
    kb.add_document("d1", "a.txt", 10, load_and_split(str(p), "d1", "a.txt"))

    kb.delete_document("d1")

    assert kb._bm25.size == 0
    assert kb.is_empty
