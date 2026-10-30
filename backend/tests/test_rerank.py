"""rerank 模块单元测试：打分解析、排序正确性、各种异常兜底。"""
import json

from langchain_core.documents import Document

from app.agent.llm import AssistantTurn
from app.agent.rerank import MIN_CANDIDATES_FOR_RERANK, rerank


class _FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0
        self.seen_messages = []

    def chat(self, messages, tools=None):
        self.calls += 1
        self.seen_messages.append(messages)
        return AssistantTurn(content=self.content)

    def stream(self, messages):
        yield self.content


class _RaisingLLM:
    def chat(self, messages, tools=None):
        raise RuntimeError("超时")

    def stream(self, messages):
        yield ""


def _docs(*texts):
    return [Document(page_content=t, metadata={"chunk_id": f"c{i}"}) for i, t in enumerate(texts)]


# ---------- 基本排序 ----------


def test_rerank_reorders_by_score():
    docs = _docs("不相关内容", "完全匹配答案")
    llm = _FakeLLM(json.dumps([2, 9]))

    result = rerank(llm, "查询", docs)

    assert result[0].page_content == "完全匹配答案"
    assert result[1].page_content == "不相关内容"


def test_rerank_keeps_order_when_scores_equal():
    docs = _docs("A", "B", "C")
    llm = _FakeLLM(json.dumps([5, 5, 5]))

    result = rerank(llm, "查询", docs)

    assert [d.page_content for d in result] == ["A", "B", "C"]


def test_rerank_handles_markdown_fence():
    docs = _docs("低分", "高分")
    llm = _FakeLLM("```json\n[1, 10]\n```")

    result = rerank(llm, "查询", docs)

    assert result[0].page_content == "高分"


# ---------- 跳过条件 ----------


def test_rerank_skips_single_candidate():
    docs = _docs("唯一的一条")
    llm = _FakeLLM("不会被调用")

    result = rerank(llm, "查询", docs)

    assert result == docs
    assert llm.calls == 0


def test_rerank_skips_empty_candidates():
    llm = _FakeLLM("不会被调用")

    result = rerank(llm, "查询", [])

    assert result == []
    assert llm.calls == 0


def test_min_candidates_constant_is_two():
    assert MIN_CANDIDATES_FOR_RERANK == 2


# ---------- 异常兜底：全部原样返回，不让 rerank 变成故障点 ----------


def test_rerank_falls_back_on_llm_exception():
    docs = _docs("A", "B")

    result = rerank(_RaisingLLM(), "查询", docs)

    assert result == docs


def test_rerank_falls_back_on_invalid_json():
    docs = _docs("A", "B")
    llm = _FakeLLM("这不是分数数组")

    result = rerank(llm, "查询", docs)

    assert result == docs


def test_rerank_falls_back_on_wrong_length():
    """模型打分数量和候选数不一致时，不能瞎对应，原样返回更安全。"""
    docs = _docs("A", "B", "C")
    llm = _FakeLLM(json.dumps([1, 2]))

    result = rerank(llm, "查询", docs)

    assert result == docs


def test_rerank_falls_back_on_non_numeric_scores():
    docs = _docs("A", "B")
    llm = _FakeLLM(json.dumps(["高", "低"]))

    result = rerank(llm, "查询", docs)

    assert result == docs


def test_rerank_falls_back_on_empty_content():
    docs = _docs("A", "B")
    llm = _FakeLLM("")

    result = rerank(llm, "查询", docs)

    assert result == docs


def test_rerank_prompt_includes_truncated_snippets():
    """超长片段应被截断，避免把整份文档塞进 rerank prompt 浪费 token。"""
    long_text = "x" * 1000
    docs = _docs(long_text, "短文本")
    llm = _FakeLLM(json.dumps([1, 9]))

    rerank(llm, "查询", docs)

    sent_content = llm.seen_messages[0][0]["content"]
    assert "…" in sent_content
    assert len(sent_content) < len(long_text) + 500
