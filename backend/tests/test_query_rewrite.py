"""query_rewrite 模块单元测试：启发式触发、LLM 拆解解析、各种异常输入的兜底。"""
import json

from app.agent.llm import AssistantTurn
from app.agent.query_rewrite import decompose_question, should_attempt_decompose


class _FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        return AssistantTurn(content=self.content)

    def stream(self, messages):
        yield self.content


class _RaisingLLM:
    def chat(self, messages, tools=None):
        raise RuntimeError("网络超时")

    def stream(self, messages):
        yield ""


# ---------- 启发式触发 ----------


def test_heuristic_triggers_on_fenbei():
    assert should_attempt_decompose("产品A和产品B的月费分别是多少？") is True


def test_heuristic_triggers_on_compare_cue():
    assert should_attempt_decompose("产品A和产品B哪个更便宜？") is True


def test_heuristic_skips_simple_question():
    assert should_attempt_decompose("产品A的月费是多少？") is False


def test_heuristic_skips_conjunction_without_compare_cue():
    # 有"和"但没有比较类线索词，不应误判为复合问题
    assert should_attempt_decompose("请介绍一下产品A和它的使用说明") is False


def test_heuristic_skips_unrelated_question():
    assert should_attempt_decompose("今天天气怎么样") is False


# ---------- LLM 拆解 ----------


def test_decompose_parses_json_array():
    llm = _FakeLLM(json.dumps(["产品A的月费是多少？", "产品B的月费是多少？"], ensure_ascii=False))

    result = decompose_question(llm, "产品A和产品B的月费分别是多少？")

    assert result == ["产品A的月费是多少？", "产品B的月费是多少？"]
    assert llm.calls == 1


def test_decompose_strips_markdown_fence():
    """模型偶尔会把 JSON 包在代码块里，要能正确抠出来。"""
    llm = _FakeLLM('```json\n["问题A", "问题B"]\n```')

    result = decompose_question(llm, "原问题")

    assert result == ["问题A", "问题B"]


def test_decompose_single_question_passthrough():
    llm = _FakeLLM(json.dumps(["原问题"], ensure_ascii=False))

    result = decompose_question(llm, "原问题")

    assert result == ["原问题"]


def test_decompose_dedupes_repeated_subquery():
    llm = _FakeLLM(json.dumps(["问题A", "问题A", "问题B"], ensure_ascii=False))

    result = decompose_question(llm, "原问题")

    assert result == ["问题A", "问题B"]


def test_decompose_caps_at_max_subqueries():
    llm = _FakeLLM(json.dumps([f"问题{i}" for i in range(10)], ensure_ascii=False))

    result = decompose_question(llm, "原问题")

    assert len(result) == 4


def test_decompose_falls_back_on_invalid_json():
    llm = _FakeLLM("这不是 JSON，是一段解释文字")

    result = decompose_question(llm, "原问题")

    assert result == ["原问题"]


def test_decompose_falls_back_on_empty_array():
    llm = _FakeLLM("[]")

    result = decompose_question(llm, "原问题")

    assert result == ["原问题"]


def test_decompose_falls_back_on_non_list_json():
    llm = _FakeLLM(json.dumps({"not": "a list"}))

    result = decompose_question(llm, "原问题")

    assert result == ["原问题"]


def test_decompose_falls_back_on_empty_content():
    llm = _FakeLLM("")

    result = decompose_question(llm, "原问题")

    assert result == ["原问题"]


def test_decompose_falls_back_on_llm_exception():
    """LLM 调用本身抛异常（网络问题等）不能让整个 Agent 崩溃。"""
    result = decompose_question(_RaisingLLM(), "原问题")

    assert result == ["原问题"]


def test_decompose_filters_blank_entries():
    llm = _FakeLLM(json.dumps(["问题A", "  ", ""], ensure_ascii=False))

    result = decompose_question(llm, "原问题")

    assert result == ["问题A"]
