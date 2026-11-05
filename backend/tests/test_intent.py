"""规则意图识别与 runner 分流测试：全部使用假 LLM 和假 Embedding，不访问外网。"""
import json

import pytest

from app.agent.intent import CHAT, KB_QUERY, LIST_DOCS, UNCERTAIN, classify
from app.agent.llm import AssistantTurn, ToolCall
from app.agent.runner import LOG_FILE, run_agent
from tests.test_agent import ScriptedLLM, _kb, _types


# ---------- 1. 规则分类 ----------


@pytest.mark.parametrize(
    "question",
    ["你好", "您好！", "hi", "Hello~", "谢谢", "谢谢你！", "好的", "收到", "再见", "你是谁", "你能做什么？", "早上好"],
)
def test_chat_greetings(question):
    assert classify(question).intent == CHAT


@pytest.mark.parametrize(
    "question",
    [
        "你好，产品A的月费是多少？",   # 寒暄夹带真实问题，不能当闲聊
        "谢谢，那产品B呢？",
        "你好你好你好你好你好你好你好你好你好你好你好",  # 超长，不当闲聊
        "好的产品有哪些",
    ],
)
def test_chat_with_real_question_is_not_chat(question):
    assert classify(question).intent != CHAT


@pytest.mark.parametrize(
    "question",
    ["知识库里有哪些文档？", "知识库中都有什么内容", "上传了哪些文件", "有哪些文档"],
)
def test_list_docs(question):
    assert classify(question).intent == LIST_DOCS


@pytest.mark.parametrize(
    "question",
    ["配置 6145 对应哪个产品？", "配置6152的负责人是谁", "GB1001 这个型号的标准容量是多少？", "工单#12345 怎么处理"],
)
def test_kb_query_with_id(question):
    result = classify(question)
    assert result.intent == KB_QUERY
    assert "编号" in result.reason


def test_kb_query_with_doc_hint():
    assert classify("根据文档里的说明，退订要提前几天？").intent == KB_QUERY


@pytest.mark.parametrize(
    "question",
    ["产品A的月费是多少？", "什么是蛋白质", "量子纠缠在生物体内的作用机制是什么？", ""],
)
def test_uncertain_goes_to_model(question):
    result = classify(question)
    assert result.intent == UNCERTAIN
    assert result.skip_llm_decision is False


def test_classify_on_eval_questions_never_mislabels_as_chat():
    """评测集里的问题都是真实提问，一条都不能被误判成闲聊（宁漏判不误判）。"""
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "cases.jsonl")
    with open(path, encoding="utf-8") as f:
        cases = [json.loads(l) for l in f if l.strip() and not l.startswith("#")]
    assert cases
    for case in cases:
        assert classify(case["question"]).intent != CHAT, case["question"]


# ---------- 2. runner 分流 ----------


def test_chat_skips_tools_and_search(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(turns=[], answer_chunks=["你好！", "有什么可以帮你？"])

    events = list(run_agent("你好", kb, llm, log_dir=None, enable_intent=True))

    types = _types(events)
    assert types[0] == "intent"
    assert events[0]["intent"] == CHAT
    assert "tool_call" not in types
    assert llm.chat_calls == 0          # 没有走带工具的决策调用
    assert llm.stream_calls == 1        # 只流式回复了一次
    assert events[-1]["type"] == "final"
    assert events[-1]["answer"] == "你好！有什么可以帮你？"
    assert events[-1]["sources"] == []


def test_chat_works_on_empty_kb(tmp_path, embeddings):
    from app.document import KnowledgeBase

    kb = KnowledgeBase(str(tmp_path / "empty"), embeddings)
    llm = ScriptedLLM(turns=[], answer_chunks=["你好"])

    events = list(run_agent("你好", kb, llm, log_dir=None, answer_mode="strict", enable_intent=True))

    assert events[-1]["type"] == "final"
    assert events[-1]["answer"] == "你好"


def test_list_docs_without_llm(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(turns=[])

    events = list(run_agent("知识库里有哪些文档？", kb, llm, log_dir=None, enable_intent=True))

    assert llm.chat_calls == 0 and llm.stream_calls == 0  # 完全不调大模型
    calls = [e for e in events if e["type"] == "tool_call"]
    assert [c["name"] for c in calls] == ["list_documents"]
    answer = events[-1]["answer"]
    assert "共有 2 个文档" in answer
    assert "a.txt" in answer and "b.txt" in answer


def test_kb_query_pre_searches_then_react(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings, texts=[("cfg.txt", "配置 6145 对应产品A的推送任务")])
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="预检索结果已经够了。", tool_calls=[])],
        answer_chunks=["配置 6145 对应产品A [E1]"],
    )

    events = list(run_agent("配置 6145 对应哪个产品？", kb, llm, log_dir=None, enable_intent=True))

    assert events[0]["intent"] == KB_QUERY
    first_call = next(e for e in events if e["type"] == "tool_call")
    assert first_call["id"] == "intent-1"
    assert first_call["args"] == {"query": "配置 6145 对应哪个产品？"}
    # 预检索结果作为一条消息交给模型
    first_messages = llm.seen_messages[0]
    assert any("系统已用原问题预先检索" in m["content"] for m in first_messages if m["role"] == "user")
    assert events[-1]["type"] == "final"
    assert events[-1]["sources"]


def test_kb_query_duplicate_search_is_short_circuited(tmp_path, embeddings):
    """模型拿原问题再查一遍时直接短路，不重复检索。"""
    kb = _kb(tmp_path, embeddings, texts=[("cfg.txt", "配置 6145 对应产品A的推送任务")])
    q = "配置 6145 对应哪个产品？"
    dup = ToolCall(id="c1", name="search_kb", arguments=json.dumps({"query": q}, ensure_ascii=False))
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="再查一次", tool_calls=[dup]), AssistantTurn(content="够了", tool_calls=[])],
        answer_chunks=["产品A [E1]"],
    )

    events = list(run_agent(q, kb, llm, log_dir=None, enable_intent=True))

    dup_result = next(e for e in events if e["type"] == "tool_result" and e["id"] == "c1")
    assert dup_result["ok"] is False
    assert "完全相同" in dup_result["summary"]


def test_uncertain_keeps_original_react_flow(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="查苹果", tool_calls=[ToolCall(id="c1", name="search_kb",
                                                                       arguments='{"query": "苹果"}')])],
        answer_chunks=["苹果是一种水果 [E1]"],
    )

    events = list(run_agent("苹果是什么", kb, llm, log_dir=None, enable_intent=True))

    assert events[0]["intent"] == UNCERTAIN
    calls = [e for e in events if e["type"] == "tool_call"]
    assert [c["id"] for c in calls] == ["c1"]  # 没有预检索，完全由模型决定


def test_intent_disabled_keeps_old_behavior(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(turns=[AssistantTurn(content="直接回答", tool_calls=[])])

    events = list(run_agent("你好", kb, llm, log_dir=None))

    assert "intent" not in _types(events)
    assert llm.chat_calls == 1  # 关闭时仍走原 ReAct 流程


def test_intent_written_to_run_log(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(turns=[], answer_chunks=["你好"])
    log_dir = tmp_path / "logs"

    list(run_agent("你好", kb, llm, log_dir=str(log_dir), enable_intent=True))

    record = json.loads((log_dir / LOG_FILE).read_text(encoding="utf-8").splitlines()[-1])
    assert record["intent"] == CHAT
