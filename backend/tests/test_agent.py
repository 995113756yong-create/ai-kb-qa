"""Agent 单元测试：全部使用 ScriptedLLM 和假 Embedding，不访问外网。"""
import json
from typing import Iterator, List, Optional

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.agent.evidence import EvidenceRegistry
from app.agent.llm import AssistantTurn, ToolCall
from app.agent.runner import LOG_FILE, run_agent
from app.agent.sse import format_event
from app.document import KnowledgeBase, load_and_split
from app.main import create_app
from app.qa import EMPTY_KB_ANSWER, NOT_FOUND_ANSWER


class ScriptedLLM:
    """按脚本依次吐 AssistantTurn，stream 则把预设文本切成几段；记录收到的 messages 供断言。"""

    def __init__(self, turns: List[AssistantTurn], answer_chunks: Optional[List[str]] = None):
        self.turns = list(turns)
        self.answer_chunks = answer_chunks or ["根据文档，", "答案是 42 [E1]"]
        self.seen_messages: List[List[dict]] = []
        self.chat_calls = 0
        self.stream_calls = 0
        self.streamed_messages: List[List[dict]] = []

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None) -> AssistantTurn:
        self.seen_messages.append(list(messages))
        self.chat_calls += 1
        if self.turns:
            return self.turns.pop(0)
        # 脚本用尽后模拟“模型不再调用工具”
        return AssistantTurn(content="信息足够，开始回答。", tool_calls=[])

    def stream(self, messages: List[dict]) -> Iterator[str]:
        self.stream_calls += 1
        self.streamed_messages.append(list(messages))
        for chunk in self.answer_chunks:
            yield chunk


def _search_call(call_id: str = "c1", query: str = "苹果") -> ToolCall:
    return ToolCall(id=call_id, name="search_kb", arguments=json.dumps({"query": query}, ensure_ascii=False))


def _kb(tmp_path, embeddings, texts=None) -> KnowledgeBase:
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    for i, text in enumerate(texts or [("a.txt", "苹果是一种水果"), ("b.txt", "火星是一颗行星")]):
        name, body = text
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        chunks = load_and_split(str(path), f"d{i}", name)
        kb.add_document(f"d{i}", name, len(body), chunks)
    return kb


def _events(gen) -> List[dict]:
    return list(gen)


def _types(events: List[dict]) -> List[str]:
    return [e["type"] for e in events]


# ---------- 1. 多步检索 ----------


def test_multi_step_search(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[
            AssistantTurn(content="先检索苹果", tool_calls=[_search_call("c1", "苹果")]),
            AssistantTurn(content="再检索火星", tool_calls=[_search_call("c2", "火星")]),
            AssistantTurn(content="信息足够。", tool_calls=[]),
        ],
        answer_chunks=["苹果是一种水果 [E1]", "，火星是一颗行星 [E2]。"],
    )

    events = _events(run_agent("对比苹果和火星", kb, llm, max_steps=6, log_dir=None))

    # 两轮都是 step -> thought -> tool_call -> tool_result
    assert _types(events) == [
        "step", "thought", "tool_call", "tool_result",
        "step", "thought", "tool_call", "tool_result",
        "step", "thought",
        "answer_delta", "answer_delta",
        "final",
    ]
    final = events[-1]
    assert len(final["sources"]) == 2
    assert [s["index"] for s in final["sources"]] == [1, 2]
    # 回答里的 [E1]/[E2] 已重编为 [1]/[2]
    assert final["answer"] == "苹果是一种水果 [1]，火星是一颗行星 [2]。"
    assert final["grounded"] is True and final["steps"] == 3
    assert llm.stream_calls == 1


# ---------- 2. 编造的引用被剔除 ----------


def test_fabricated_citation_removed(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="", tool_calls=[_search_call()]), AssistantTurn(content="够了")],
        answer_chunks=["苹果是水果 [E1]，", "香蕉也是水果 [E9]。"],
    )

    final = _events(run_agent("苹果", kb, llm, log_dir=None))[-1]

    assert "[E9]" not in final["answer"] and "[9]" not in final["answer"]
    assert len(final["sources"]) == 1
    assert final["answer"] == "苹果是水果 [1]，香蕉也是水果 。"


# ---------- 3. 没有有效引用 ----------


def test_no_citation_marks_ungrounded(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="", tool_calls=[_search_call()]), AssistantTurn(content="够了")],
        answer_chunks=["苹果是一种水果。"],
    )

    final = _events(run_agent("苹果", kb, llm, log_dir=None))[-1]

    assert final["sources"] == []
    assert final["grounded"] is False


# ---------- 4. 没有证据 ----------


def test_no_evidence_returns_not_found(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(turns=[AssistantTurn(content="我不知道，直接回答。", tool_calls=[])])

    final = _events(run_agent("无关问题", kb, llm, log_dir=None))[-1]

    assert final["answer"] == NOT_FOUND_ANSWER
    assert final["sources"] == [] and final["grounded"] is True
    assert llm.stream_calls == 0


# ---------- 5. 知识库为空 ----------


def test_empty_kb_skips_llm(tmp_path, embeddings):
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    llm = ScriptedLLM(turns=[])

    final = _events(run_agent("任意问题", kb, llm, log_dir=None))[-1]

    assert final["answer"] == EMPTY_KB_ANSWER
    assert llm.chat_calls == 0 and llm.stream_calls == 0


# ---------- 6. 工具参数错误 ----------


def test_bad_tool_arguments_keeps_loop(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    bad = ToolCall(id="c1", name="search_kb", arguments="{不是 JSON")
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="", tool_calls=[bad]), AssistantTurn(content="放弃")],
        answer_chunks=["随便答 [E1]"],
    )

    events = _events(run_agent("苹果", kb, llm, log_dir=None))

    results = [e for e in events if e["type"] == "tool_result"]
    assert len(results) == 1 and results[0]["ok"] is False
    assert "JSON" in results[0]["summary"]
    # 工具消息里必须是 error 对象，供模型自我修正
    tool_messages = [m for m in llm.seen_messages[1] if m["role"] == "tool"]
    assert "error" in json.loads(tool_messages[0]["content"])


# ---------- 7. 重复调用 ----------


def test_duplicate_call_short_circuits(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[
            AssistantTurn(content="", tool_calls=[_search_call("c1")]),
            AssistantTurn(content="", tool_calls=[_search_call("c2")]),
            AssistantTurn(content="够了"),
        ],
    )

    events = _events(run_agent("苹果", kb, llm, log_dir=None))

    results = [e for e in events if e["type"] == "tool_result"]
    assert len(results) == 2
    assert results[0]["ok"] is True
    assert results[1]["ok"] is False and "结果同上" in results[1]["summary"]


# ---------- 8. 最大步数 ----------


def test_max_steps_cap(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    # 每次都换关键词，避免被重复调用拦截
    turns = [
        AssistantTurn(content="", tool_calls=[_search_call(f"c{i}", f"苹果{i}")]) for i in range(5)
    ]
    llm = ScriptedLLM(turns=turns)

    events = _events(run_agent("苹果", kb, llm, max_steps=3, log_dir=None))

    steps = sorted({e["step"] for e in events if e["type"] == "step"})
    assert steps == [1, 2, 3]
    assert llm.chat_calls == 3
    # 达到上限后仍要进入回答阶段
    assert any(e["type"] == "answer_delta" for e in events)


# ---------- 9. 连续 3 次工具错误 ----------


def test_consecutive_errors_stop_early(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings)
    bad = [
        ToolCall(id=f"c{i}", name="search_kb", arguments="not json") for i in range(5)
    ]
    llm = ScriptedLLM(turns=[AssistantTurn(content="", tool_calls=[call]) for call in bad])

    events = _events(run_agent("苹果", kb, llm, max_steps=6, log_dir=None))

    assert len([e for e in events if e["type"] == "tool_result"]) == 3
    assert llm.chat_calls == 3


# ---------- 10. SSE 接口 ----------


@pytest.fixture
def agent_client(tmp_path, embeddings):
    """构造 TestClient；必须进 with 触发 lifespan，否则 app.state 里的服务都还是 None。"""
    opened = []

    def _make(agent_llm, log_dir=None):
        app = create_app(
            embeddings=embeddings,
            # 固定 RAG 的 llm 必须是 LangChain Runnable，Agent 的 llm 只需要满足 AgentLLM 协议
            llm=FakeListChatModel(responses=["固定 RAG 的假回答 [1]"]),
            upload_dir=str(tmp_path / "uploads"),
            index_dir=str(tmp_path / "idx"),
            agent_llm=agent_llm,
            agent_log_dir=log_dir,
        )
        client = TestClient(app)
        client.__enter__()
        opened.append(client)
        return client

    yield _make

    for client in opened:
        client.__exit__(None, None, None)


def _parse_sse(body: str) -> List[dict]:
    events = []
    for block in body.split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue
        lines = block.strip().split("\n")
        event_type = next(l[7:] for l in lines if l.startswith("event: "))
        data = next(l[6:] for l in lines if l.startswith("data: "))
        events.append({"event": event_type, "data": json.loads(data)})
    return events


def test_agent_stream_endpoint(agent_client):
    llm = ScriptedLLM(
        turns=[
            AssistantTurn(content="先查一下苹果", tool_calls=[_search_call()]),
            AssistantTurn(content="够了"),
        ],
        answer_chunks=["苹果是水果 [E1]"],
    )
    client = agent_client(llm)

    client.post("/api/upload", files={"file": ("a.txt", "苹果是一种水果".encode("utf-8"), "text/plain")})
    resp = client.post("/api/agent/stream", json={"question": "苹果是什么？"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"

    events = _parse_sse(resp.text)
    assert [e["event"] for e in events] == [
        "step", "thought", "tool_call", "tool_result", "step", "thought", "answer_delta", "final",
    ]
    assert events[-1]["data"]["answer"] == "苹果是水果 [1]"
    assert events[-1]["data"]["sources"][0]["source"] == "a.txt"


def test_agent_stream_requires_api_key(tmp_path, embeddings, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "OPENAI_API_KEY", None)
    app = create_app(upload_dir=str(tmp_path / "u"), index_dir=str(tmp_path / "i"))
    with TestClient(app) as client:
        assert client.post("/api/agent/stream", json={"question": "hi"}).status_code == 503


def test_agent_stream_validates_question(agent_client):
    client = agent_client(ScriptedLLM(turns=[]))
    assert client.post("/api/agent/stream", json={"question": ""}).status_code == 422
    assert client.post("/api/agent/stream", json={"question": "x" * 1001}).status_code == 422


def test_format_event_shape():
    text = format_event({"type": "thought", "step": 1, "text": "思考"})
    assert text.startswith("event: thought\ndata: ")
    assert text.endswith("\n\n")


# ---------- 11. 运行日志 ----------


def test_run_log_written(tmp_path, embeddings):
    log_dir = tmp_path / "logs"
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="", tool_calls=[_search_call()]), AssistantTurn(content="够了")],
        answer_chunks=["苹果是水果 [E1]"],
    )

    _events(run_agent("苹果", kb, llm, log_dir=str(log_dir)))

    log_file = log_dir / LOG_FILE
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["grounded"] is True
    assert record["question"] == "苹果"
    assert record["evidence_count"] == 2
    assert record["steps"][0]["tool"] == "search_kb"


# ---------- evidence 细节 ----------


def test_registry_dedupes_same_chunk(tmp_path, embeddings):
    kb = _kb(tmp_path, embeddings, [("a.txt", "苹果是一种水果")])
    registry = EvidenceRegistry()
    doc = kb.search("苹果", k=1)[0]

    first = registry.register(doc)
    second = registry.register(doc)

    assert first.evidence_id == second.evidence_id == "E1"
    assert len(registry) == 1


# ---------- 多编号引用 ----------


def test_multi_id_citation_in_one_bracket(tmp_path, embeddings):
    """模型常写 [E1, E2]，应合并重编为 [1][2]，编造的 E9 必须剔除。"""
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="", tool_calls=[_search_call()]), AssistantTurn(content="够了")],
        answer_chunks=["苹果是水果 [E1, E2]，香蕉 [E9]，火星是行星 [E2、E3]。"],
    )

    final = _events(run_agent("苹果", kb, llm, log_dir=None))[-1]

    assert final["answer"] == "苹果是水果 [1][2]，香蕉 ，火星是行星 [2]。"
    assert len(final["sources"]) == 2
    assert final["grounded"] is True


def test_duplicate_ids_are_collapsed():
    """同一括号里重复的编号只保留一次。"""
    from app.agent.evidence import EvidenceRegistry
    from langchain_core.documents import Document

    registry = EvidenceRegistry()
    registry.register(Document(page_content="甲", metadata={"doc_id": "d", "chunk_index": 0, "chunk_id": "d:0"}))
    registry.register(Document(page_content="乙", metadata={"doc_id": "d", "chunk_index": 1, "chunk_id": "d:1"}))

    clean, sources, grounded = registry.finalize("结论 [E1, E1]。")

    assert clean == "结论 [1]。"
    assert len(sources) == 1 and grounded is True


def test_agent_stream_missing_key_returns_503(tmp_path, monkeypatch):
    """CI 里没有 .env，未配 Key 时应用要能启动，Agent 接口返回 503 而不是启动就崩。"""
    from app import config

    monkeypatch.setattr(config, "OPENAI_API_KEY", None)
    app = create_app(upload_dir=str(tmp_path / "u"), index_dir=str(tmp_path / "i"))

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/agent/stream", json={"question": "hi"}).status_code == 503
