"""统一检索 retrieve() 与证据门槛测试."""
import json

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from app import config
from app.agent.evidence import EvidenceRegistry
from app.agent.llm import AssistantTurn, ToolCall
from app.agent.tools import execute_tool
from app.document import KnowledgeBase, has_keyword_hit, identifier_tokens, load_and_split


def _add(kb: KnowledgeBase, tmp_path, name: str, text: str, doc_id: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    chunks = load_and_split(str(path), doc_id, name)
    kb.add_document(doc_id, name, len(text), chunks)


@pytest.fixture
def kb(tmp_path):
    kb = KnowledgeBase(str(tmp_path / "idx"), DeterministicFakeEmbedding(size=32))
    _add(kb, tmp_path, "a.txt", "苹果是一种水果，富含维生素", "d1")
    _add(kb, tmp_path, "b.txt", "香蕉是黄色的水果，富含钾元素", "d2")
    return kb


# ---------- retrieve 基础 ----------


def test_retrieve_returns_hits_with_sim(kb):
    hits = kb.retrieve("苹果是一种水果，富含维生素", k=2)
    assert hits
    # 用片段原文作为查询时，同文本同向量，余弦应接近 1
    assert hits[0].vector_sim >= 0.99


def test_retrieve_vector_sim_normalization_independent(tmp_path):
    """vector_sim 与向量是否归一化无关：向量全体乘 10 后余弦不变。"""

    from langchain_core.embeddings import Embeddings

    base = DeterministicFakeEmbedding(size=32)

    class ScaledEmbeddings(Embeddings):
        """包装：把每个向量乘以 10（破坏归一化状态）。必须继承 Embeddings，FAISS 会 isinstance 检查。"""

        def embed_query(self, text):
            return [x * 10 for x in base.embed_query(text)]

        def embed_documents(self, texts):
            return [[x * 10 for x in v] for v in base.embed_documents(texts)]

    kb1 = KnowledgeBase(str(tmp_path / "n1"), base)
    kb2 = KnowledgeBase(str(tmp_path / "n2"), ScaledEmbeddings())
    for kb_, d in ((kb1, "k1"), (kb2, "k2")):
        _add(kb_, tmp_path, "s.txt", "苹果是一种水果，富含维生素", d)

    q = "苹果是一种水果，富含维生素"
    sim1 = kb1.retrieve(q, k=1)[0].vector_sim
    sim2 = kb2.retrieve(q, k=1)[0].vector_sim
    assert abs(sim1 - sim2) < 1e-4


def test_retrieve_after_delete_still_correct(kb, tmp_path):
    """删除文档后反查表失效重建，vector_sim 仍然正确。"""
    before = kb.retrieve("香蕉是黄色的水果，富含钾元素", k=2)
    assert before
    kb.delete_document("d1")
    after = kb.retrieve("香蕉是黄色的水果，富含钾元素", k=2)
    assert after
    assert all((h.doc.metadata or {}).get("doc_id") == "d2" for h in after)
    assert after[0].vector_sim >= 0.99


def test_retrieve_doc_id_filter(kb, tmp_path):
    _add(kb, tmp_path, "big.txt", "梨是水果。梨有很多品种。梨的水分充足。" * 10, "d3")
    hits = kb.retrieve("水果", k=10, doc_id="d2")
    assert hits
    assert all((h.doc.metadata or {}).get("doc_id") == "d2" for h in hits)


def test_retrieve_empty_kb(tmp_path):
    kb = KnowledgeBase(str(tmp_path / "empty"), DeterministicFakeEmbedding(size=32))
    assert kb.retrieve("任何", k=3) == []


# ---------- identifier tokens ----------


def test_identifier_tokens():
    assert identifier_tokens("配置 6145 是谁负责") == ["6145"]
    assert identifier_tokens("GB1001 的标准容量") == ["gb1001"]
    assert identifier_tokens("X-200 型号有什么限制") == ["x-200"]
    assert identifier_tokens("产品A") == []
    assert identifier_tokens("型号 AB 没有") == []  # 无数字不算


def test_has_keyword_hit():
    assert has_keyword_hit(["6145"], "配置 6145 的负责人")
    assert not has_keyword_hit(["6145"], "配置 61450 的负责人")  # 词边界
    assert not has_keyword_hit([], "任何文本")


# ---------- 证据门槛 ----------


def _search(kb, query, k=5):
    registry = EvidenceRegistry()
    result = execute_tool(
        "search_kb", json.dumps({"query": query, "k": k}, ensure_ascii=False), kb, registry
    )
    return result


def test_threshold_blocks_irrelevant(kb, monkeypatch):
    monkeypatch.setattr(config, "EVIDENCE_MIN_SIM", 0.99)
    result = _search(kb, "量子纠缠的原理")
    assert result["items"] == []
    assert "阈值" in result["message"]


def test_threshold_keyword_bypass(kb, tmp_path, monkeypatch):
    """查询里的编号关键词命中片段时，即使相似度低也通过门槛。"""
    monkeypatch.setattr(config, "EVIDENCE_MIN_SIM", 0.99)
    _add(kb, tmp_path, "conf.txt", "配置 6145 负责人是 zhangsan，任务每周执行", "d9")
    result = _search(kb, "配置 6145 是谁负责", k=5)
    assert result["items"], "编号关键词应绕过余弦门槛"
    assert result["items"][0]["match"] == "keyword"


def test_threshold_off_by_default(kb):
    """conftest 全局关闭门槛（-1）：正常检索不受影响。"""
    assert config.EVIDENCE_MIN_SIM < 0
    result = _search(kb, "苹果")
    assert result["items"]


def test_search_returns_relevance_and_match(kb):
    result = _search(kb, "苹果是一种水果，富含维生素")
    assert result["items"]
    assert "relevance" in result["items"][0]
    assert result["items"][0]["match"] in ("keyword", "semantic")
    assert "scores" in result


# ---------- 回归：search() 走 retrieve ----------


def test_search_compatibility(kb):
    """search() 走 retrieve()：混合检索下关键词命中的文档应排在前。"""
    docs = kb.search("苹果是一种水果，富含维生素", k=2)
    assert docs
    assert (docs[0].metadata or {}).get("source") == "a.txt"
    # 原 query 原文检索时第一名必须是原文所在文档
    assert kb.search("苹果是一种水果，富含维生素", k=1)[0].page_content.startswith("苹果")
