"""多轮追问改写。

历史只用来改写问题，不进入研究和回答阶段：证据边界与单轮完全一致。
"""
import json

import pytest

from app import config
from app.agent.contextualize import (
    MAX_REWRITE_LEN,
    build_rewrite_messages,
    contextualize,
    looks_like_followup,
)
from app.agent.llm import AssistantTurn


class RewriteLLM:
    """只实现 chat，返回预设文本；用于改写单测。"""

    def __init__(self, text="", raises=None):
        self.text = text
        self.raises = raises
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        if self.raises:
            raise self.raises
        return AssistantTurn(content=self.text)

    def stream(self, messages):  # pragma: no cover - 改写不走流式
        yield self.text


HISTORY = [
    {"role": "user", "content": "产品 A 的月费是多少？"},
    {"role": "assistant", "content": "产品 A 的月费是 30 元 [1]。"},
]


# ---------- looks_like_followup ----------

def test_no_history_never_rewrites():
    assert looks_like_followup("那产品 B 呢？", []) is False


@pytest.mark.parametrize(
    "q",
    ["那产品 B 呢？", "展开说说第二点", "它支持单点登录吗", "还有别的吗", "对比一下"],
)
def test_followup_detected(q):
    assert looks_like_followup(q, HISTORY) is True


def test_plain_question_not_rewritten():
    # 超过 12 字且不含追问特征
    assert looks_like_followup("产品A的月费是多少钱一个月呢", HISTORY) is True  # 含"呢"
    assert looks_like_followup("请介绍一下产品的价格体系和计费方式", HISTORY) is False


# ---------- contextualize ----------

def test_returns_rewritten_text():
    llm = RewriteLLM("产品 B 的月费是多少？")
    assert contextualize(llm, "那产品 B 呢？", HISTORY, 3) == "产品 B 的月费是多少？"


@pytest.mark.parametrize("bad", ["", "   ", "x" * (MAX_REWRITE_LEN + 1)])
def test_bad_output_returns_none(bad):
    assert contextualize(RewriteLLM(bad), "那产品 B 呢？", HISTORY, 3) is None


def test_same_as_question_returns_none():
    q = "那产品 B 呢？"
    assert contextualize(RewriteLLM(q), q, HISTORY, 3) is None


def test_exception_returns_none():
    llm = RewriteLLM(raises=RuntimeError("boom"))
    assert contextualize(llm, "那产品 B 呢？", HISTORY, 3) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("改写后的问题：产品 B 的月费是多少？", "产品 B 的月费是多少？"),
        ('"产品 B 的月费是多少？"', "产品 B 的月费是多少？"),
        ("“产品 B 的月费是多少？”", "产品 B 的月费是多少？"),
    ],
)
def test_strips_prefix_and_quotes(raw, expected):
    assert contextualize(RewriteLLM(raw), "那产品 B 呢？", HISTORY, 3) == expected


def test_not_followup_skips_llm_call():
    """不含追问特征的长问题直接跳过，不产生额外的 LLM 调用。"""
    llm = RewriteLLM("不应该被调用")
    q = "产品的价格体系与计费规则是怎样的"
    assert looks_like_followup(q, HISTORY) is False
    assert contextualize(llm, q, HISTORY, 3) is None
    assert llm.calls == 0


# ---------- build_rewrite_messages ----------

def test_history_truncated_to_max_turns():
    long_history = []
    for i in range(5):
        long_history.append({"role": "user", "content": f"问题{i}"})
        long_history.append({"role": "assistant", "content": f"回答{i}"})

    msgs = build_rewrite_messages("那下一个呢？", long_history, 3)
    user_msg = msgs[-1]["content"]
    # 3 轮 = 最近 6 条，最早两轮不应出现
    assert "问题0" not in user_msg
    assert "问题1" not in user_msg
    assert "问题2" in user_msg


def test_assistant_content_truncated_and_citations_stripped():
    history = [
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "很长的回答" * 300 + " [1] [E2]"},
    ]
    msgs = build_rewrite_messages("展开说说", history, 3)
    content = msgs[-1]["content"]
    assert "[1]" not in content
    assert "[E2]" not in content
    # assistant 内容被截断到 HISTORY_ANSWER_CHARS(600) 字
    assistant_part = content.split("助手：", 1)[1].split("\n\n最新问题", 1)[0]
    assert len(assistant_part) <= 600


# ---------- 端到端 ----------

def test_request_rejects_too_many_history_turns(client, tmp_path):
    payload = {
        "question": "那 B 呢",
        "history": [{"role": "user", "content": "x"} for _ in range(13)],
    }
    assert client.post("/api/agent/stream", json=payload).status_code == 422


def test_request_rejects_oversized_history_content(client):
    payload = {
        "question": "那 B 呢",
        "history": [{"role": "user", "content": "x" * 2001}],
    }
    assert client.post("/api/agent/stream", json=payload).status_code == 422


def test_no_history_keeps_single_turn_behaviour(client):
    """回归：不带 history 时不应出现 rewrite 事件。"""
    res = client.post("/api/agent/stream", json={"question": "产品A的月费是多少？"})
    assert res.status_code == 200
    assert "rewrite" not in res.text
