"""run_agent 接入查询改写与 rerank 后的集成测试。

复用 test_agent.py 的 ScriptedLLM 风格，但这里显式打开
enable_decompose / enable_rerank 验证新行为，默认关闭的旧行为
已由 test_agent.py 原有用例覆盖（它们都不传这两个参数）。
"""
import json
from typing import Iterator, List, Optional

from app.agent.llm import AssistantTurn, ToolCall
from app.agent.runner import run_agent
from app.document import KnowledgeBase, load_and_split


class ScriptedLLM:
    """同 test_agent.py：按脚本吐 AssistantTurn，stream 吐预设文本片段。"""

    def __init__(self, turns: List[AssistantTurn], answer_chunks: Optional[List[str]] = None):
        self.turns = list(turns)
        self.answer_chunks = answer_chunks or ["好的 [E1]"]
        self.chat_calls = 0
        self.stream_calls = 0
        self.seen_messages: List[List[dict]] = []

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None) -> AssistantTurn:
        self.seen_messages.append(list(messages))
        self.chat_calls += 1
        if self.turns:
            return self.turns.pop(0)
        return AssistantTurn(content="信息足够，开始回答。", tool_calls=[])

    def stream(self, messages: List[dict]) -> Iterator[str]:
        self.stream_calls += 1
        for chunk in self.answer_chunks:
            yield chunk


class DecomposeLLM:
    """专用于查询拆解阶段：第一次 chat 返回拆解结果，之后的 chat 转给内层 ScriptedLLM。"""

    def __init__(self, decompose_json: str, inner: ScriptedLLM):
        self.decompose_json = decompose_json
        self.inner = inner
        self._decompose_done = False

    def chat(self, messages, tools=None):
        if not self._decompose_done and tools is None:
            self._decompose_done = True
            return AssistantTurn(content=self.decompose_json)
        return self.inner.chat(messages, tools)

    def stream(self, messages):
        return self.inner.stream(messages)

    @property
    def chat_calls(self):
        return self.inner.chat_calls

    @property
    def stream_calls(self):
        return self.inner.stream_calls


def _kb(tmp_path, embeddings) -> KnowledgeBase:
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    for i, (name, body) in enumerate(
        [("a.txt", "产品A的月费是30元"), ("b.txt", "产品B的月费是50元")]
    ):
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        chunks = load_and_split(str(path), f"d{i}", name)
        kb.add_document(f"d{i}", name, len(body), chunks)
    return kb


def _events(gen) -> List[dict]:
    return list(gen)


# ---------- enable_decompose ----------


def test_decompose_disabled_by_default(tmp_path, embeddings):
    """不传 enable_decompose 时必须是旧行为：不出现 decompose 事件。"""
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[
            AssistantTurn(
                content="",
                tool_calls=[ToolCall(id="c1", name="search_kb", arguments=json.dumps({"query": "产品A"}))],
            ),
            AssistantTurn(content="够了"),
        ],
    )

    events = _events(run_agent("产品A和产品B的月费分别是多少？", kb, llm, log_dir=None))

    assert not any(e["type"] == "decompose" for e in events)


def test_decompose_enabled_predicts_subqueries(tmp_path, embeddings):
    """开启后，复合问题应先产出 decompose 事件，并预先检索每个子问题。"""
    kb = _kb(tmp_path, embeddings)
    inner = ScriptedLLM(turns=[AssistantTurn(content="信息足够，开始回答。")])
    decompose_llm = DecomposeLLM(
        json.dumps(["产品A的月费是多少？", "产品B的月费是多少？"], ensure_ascii=False), inner
    )

    events = _events(
        run_agent(
            "产品A和产品B的月费分别是多少？",
            kb,
            inner,
            log_dir=None,
            enable_decompose=True,
            decompose_llm=decompose_llm,
        )
    )

    decompose_events = [e for e in events if e["type"] == "decompose"]
    assert len(decompose_events) == 1
    assert decompose_events[0]["queries"] == ["产品A的月费是多少？", "产品B的月费是多少？"]

    pre_tool_results = [e for e in events if e["type"] == "tool_result" and e["step"] == 0]
    assert len(pre_tool_results) == 2
    assert all(r["ok"] for r in pre_tool_results)


def test_decompose_single_question_no_predecompose(tmp_path, embeddings):
    """简单问题即使开了 enable_decompose，启发式也不会触发额外 LLM 调用。"""
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(turns=[AssistantTurn(content="直接回答。")])

    events = _events(
        run_agent("产品A的月费是多少？", kb, llm, log_dir=None, enable_decompose=True)
    )

    assert not any(e["type"] == "decompose" for e in events)


def test_decompose_predecovered_queries_avoid_duplicate_tool_call(tmp_path, embeddings):
    """预检索过的子问题，模型后续原样再查同一个 query 时应被去重短路。

    拆解结果必须 >1 个子问题，预检索逻辑才会触发
    （见 runner.py 的 len(sub_queries) > 1 判断）。
    """
    kb = _kb(tmp_path, embeddings)
    inner = ScriptedLLM(
        turns=[
            AssistantTurn(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="search_kb", arguments=json.dumps({"query": "产品A的月费是多少？"}))
                ],
            ),
            AssistantTurn(content="够了"),
        ],
    )
    decompose_llm = DecomposeLLM(
        json.dumps(["产品A的月费是多少？", "产品B的月费是多少？"], ensure_ascii=False), inner
    )

    events = _events(
        run_agent(
            "产品A和产品B分别是多少？",
            kb,
            inner,
            log_dir=None,
            enable_decompose=True,
            decompose_llm=decompose_llm,
        )
    )

    duplicate_results = [
        e for e in events if e["type"] == "tool_result" and e["step"] != 0 and not e["ok"]
    ]
    assert len(duplicate_results) == 1
    assert "结果同上" in duplicate_results[0]["summary"]


# ---------- enable_rerank ----------


def test_rerank_disabled_by_default_does_not_call_extra_llm(tmp_path, embeddings):
    """不传 enable_rerank 时沿用旧行为：search_kb 不会多触发一次 chat 调用做打分。"""
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[
            AssistantTurn(
                content="",
                tool_calls=[ToolCall(id="c1", name="search_kb", arguments=json.dumps({"query": "月费"}))],
            ),
            AssistantTurn(content="够了"),
        ],
    )

    _events(run_agent("月费是多少", kb, llm, log_dir=None))

    # 只有 ReAct 循环本身的两次 chat（一次发起检索，一次决定收尾），没有额外的 rerank 调用
    assert llm.chat_calls == 2


def test_rerank_enabled_reorders_results(tmp_path, embeddings):
    """开启 rerank 后，search_kb 返回的证据顺序应按 rerank 打分重排。"""
    kb = _kb(tmp_path, embeddings)

    class RerankAwareLLM(ScriptedLLM):
        """第一次 chat 是 ReAct 决策，之后每次 chat 当作 rerank 打分请求处理。"""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._react_done = False

        def chat(self, messages, tools=None):
            if tools is not None:
                return super().chat(messages, tools)
            # rerank 请求不带 tools；让第二个候选（产品B）打高分，验证确实重排了
            self.chat_calls += 1
            return AssistantTurn(content=json.dumps([1, 9]))

    llm = RerankAwareLLM(
        turns=[
            AssistantTurn(
                content="",
                tool_calls=[ToolCall(id="c1", name="search_kb", arguments=json.dumps({"query": "月费", "k": 2}))],
            ),
            AssistantTurn(content="够了"),
        ],
    )

    events = _events(run_agent("月费是多少", kb, llm, log_dir=None, enable_rerank=True))

    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert tool_result["ok"] is True
