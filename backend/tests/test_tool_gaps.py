"""补齐审查指出的测试缺口：read_chunk、list_documents、SSE 心跳与断连。"""
import asyncio
import json
from typing import Any, Dict, List

import pytest

from app.agent.evidence import EvidenceRegistry
from app.agent.llm import AssistantTurn, ToolCall
from app.agent.sse import HEARTBEAT_LINE, format_event, stream_events
from app.agent.tools import execute_tool
from app.document import KnowledgeBase, load_and_split


def _kb(tmp_path, embeddings, chunks_count=3):
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    text = "".join(f"第{i}段内容，讲的是报表口径。" for i in range(chunks_count * 40))
    path = tmp_path / "doc.txt"
    path.write_text(text, encoding="utf-8")
    chunks = load_and_split(str(path), "d1", "doc.txt")
    kb.add_document("d1", "doc.txt", len(text), chunks)
    return kb, len(chunks)


# ---------- list_documents ----------


def test_tool_list_documents_empty(tmp_path, embeddings):
    kb = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    registry = EvidenceRegistry()

    result = execute_tool("list_documents", "{}", kb, registry)

    assert result["items"] == []
    assert "为空" in result["message"]


def test_tool_list_documents_with_docs(tmp_path, embeddings):
    kb, n = _kb(tmp_path, embeddings)
    registry = EvidenceRegistry()

    result = execute_tool("list_documents", "", kb, registry)

    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["doc_id"] == "d1"
    assert item["filename"] == "doc.txt"
    assert item["chunks"] == n


def test_tool_list_documents_does_not_register_evidence(tmp_path, embeddings):
    """列文档不是证据，不应该占用证据编号。"""
    kb, _ = _kb(tmp_path, embeddings)
    registry = EvidenceRegistry()

    execute_tool("list_documents", "{}", kb, registry)

    assert len(registry) == 0


# ---------- read_chunk ----------


def test_tool_read_chunk_expands_neighbors(tmp_path, embeddings):
    kb, n = _kb(tmp_path, embeddings)
    assert n >= 3, "需要至少 3 个片段才能验证相邻关系"

    registry = EvidenceRegistry()
    # 先检索拿到一个中间片段的编号
    found = execute_tool("search_kb", json.dumps({"query": "报表口径", "k": 1}), kb, registry)
    evidence_id = found["items"][0]["evidence_id"]

    result = execute_tool(
        "read_chunk", json.dumps({"evidence_id": evidence_id, "window": 1}), kb, registry
    )

    assert "error" not in result
    assert len(result["items"]) >= 1
    # 相邻片段也要登记成证据，编号继续往后排
    assert any(item["evidence_id"] != evidence_id for item in result["items"])


def test_tool_read_chunk_unknown_id(tmp_path, embeddings):
    kb, _ = _kb(tmp_path, embeddings)
    registry = EvidenceRegistry()
    execute_tool("search_kb", json.dumps({"query": "报表", "k": 1}), kb, registry)

    result = execute_tool("read_chunk", json.dumps({"evidence_id": "E99"}), kb, registry)

    assert "error" in result
    # 错误信息要告诉模型当前可用编号，方便自我修正
    assert "E1" in result["error"]


def test_tool_read_chunk_missing_id(tmp_path, embeddings):
    kb, _ = _kb(tmp_path, embeddings)
    registry = EvidenceRegistry()

    result = execute_tool("read_chunk", "{}", kb, registry)

    assert "error" in result and "evidence_id" in result["error"]


def test_tool_read_chunk_window_clamped(tmp_path, embeddings):
    """window 超出范围要被夹到 0~2，不能报错也不能越界。"""
    kb, _ = _kb(tmp_path, embeddings)
    registry = EvidenceRegistry()
    found = execute_tool("search_kb", json.dumps({"query": "报表", "k": 1}), kb, registry)
    evidence_id = found["items"][0]["evidence_id"]

    for window in (-5, 0, 99, "abc"):
        result = execute_tool(
            "read_chunk",
            json.dumps({"evidence_id": evidence_id, "window": window}),
            kb,
            registry,
        )
        assert "error" not in result, f"window={window} 时出错：{result}"
        assert 1 <= len(result["items"]) <= 5  # 自身 + 前后各 2


def test_tool_read_chunk_registry_dedupes(tmp_path, embeddings):
    """重复读同一片段不会重复分配编号。"""
    kb, _ = _kb(tmp_path, embeddings)
    registry = EvidenceRegistry()
    found = execute_tool("search_kb", json.dumps({"query": "报表", "k": 1}), kb, registry)
    evidence_id = found["items"][0]["evidence_id"]

    first = execute_tool("read_chunk", json.dumps({"evidence_id": evidence_id}), kb, registry)
    size_after_first = len(registry)
    second = execute_tool("read_chunk", json.dumps({"evidence_id": evidence_id}), kb, registry)

    assert [i["evidence_id"] for i in first["items"]] == [
        i["evidence_id"] for i in second["items"]
    ]
    assert len(registry) == size_after_first


# ---------- search_k 透传 ----------


def test_execute_tool_honours_search_k(tmp_path, embeddings):
    """P1-3 回归：run_agent 传的 search_k 要真正影响检索条数。"""
    kb, n = _kb(tmp_path, embeddings, chunks_count=8)
    assert n >= 6

    registry = EvidenceRegistry()
    result = execute_tool("search_kb", json.dumps({"query": "报表口径", "k": 2}), kb, registry)
    assert len(result["items"]) == 2

    # 未显式传 k 时用调用方给的默认值
    registry2 = EvidenceRegistry()
    result2 = execute_tool(
        "search_kb", json.dumps({"query": "报表口径"}), kb, registry2, search_k=1
    )
    assert len(result2["items"]) == 1


# ---------- SSE 心跳与断连 ----------


def _events(*payloads: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(payloads)


def _drain(gen) -> List[str]:
    """项目未引入 pytest-asyncio，用 asyncio.run 手动驱动异步生成器。"""

    async def run() -> List[str]:
        return [chunk async for chunk in gen]

    return asyncio.run(run())


def test_stream_events_emits_heartbeat_when_idle():
    """生成器长时间不产出时，应该发心跳注释行，避免代理掐断连接。"""
    import time

    def slow_gen():
        yield {"type": "step", "step": 1}
        time.sleep(0.35)  # 超过心跳间隔
        yield {"type": "final", "answer": "ok", "sources": [], "grounded": True, "steps": 1}

    chunks = _drain(stream_events(slow_gen(), heartbeat_seconds=0.1))

    assert HEARTBEAT_LINE in chunks
    # 心跳不能影响正常事件
    assert any(chunk.startswith("event: step") for chunk in chunks)
    assert any(chunk.startswith("event: final") for chunk in chunks)


def test_stream_events_stops_when_client_disconnects():
    """客户端断开后必须立刻停止，不能继续把后面的事件跑完。"""
    produced: List[int] = []

    def counting_gen():
        for i in range(50):
            produced.append(i)
            yield {"type": "step", "step": i}

    calls = {"n": 0}

    async def disconnected() -> bool:
        calls["n"] += 1
        # 前两次放行，之后视为断开
        return calls["n"] > 2

    chunks = _drain(stream_events(counting_gen(), disconnected, heartbeat_seconds=0.05))

    assert len(chunks) < 50, "断连后仍在继续产事件"
    assert len(produced) < 50, "断连后生成器仍被继续推进"


def test_stream_events_without_disconnect_hook():
    """is_disconnected 为 None 时也能正常跑完。"""

    def gen():
        yield {"type": "step", "step": 1}

    chunks = _drain(stream_events(gen()))

    assert len(chunks) == 1 and chunks[0].startswith("event: step")


def test_format_event_escapes_newlines():
    """data 里的换行必须被 JSON 转义，否则会破坏 SSE 分帧。"""
    text = format_event({"type": "thought", "step": 1, "text": "第一行\n第二行"})

    # 只应有一个空行分隔符（结尾的 \n\n），正文里的换行已被转义
    assert text.count("\n\n") == 1
    payload = json.loads(text.split("data: ", 1)[1].strip())
    assert payload["text"] == "第一行\n第二行"
