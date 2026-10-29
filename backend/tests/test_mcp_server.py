"""MCP Server 的协议一致性测试。

覆盖 JSON-RPC 分层错误、工具调用、状态隔离。
不启动真实 stdio 进程，直接测 McpServer.handle 与 serve 的读写。
"""
import io
import json

import pytest

from app.document import KnowledgeBase, load_and_split
from app.mcp_server import PROTOCOL_VERSION, McpServer, serve


@pytest.fixture
def kb(tmp_path, embeddings):
    k = KnowledgeBase(str(tmp_path / "idx"), embeddings)
    p = tmp_path / "a.txt"
    p.write_text("配置 6145 是产品A 的默认推送，负责人 zhangsan。" * 5, encoding="utf-8")
    k.add_document("d1", "a.txt", 100, load_and_split(str(p), "d1", "a.txt"))
    p2 = tmp_path / "b.txt"
    p2.write_text("苹果是一种水果，火星是一颗行星。" * 5, encoding="utf-8")
    k.add_document("d2", "b.txt", 100, load_and_split(str(p2), "d2", "b.txt"))
    return k


@pytest.fixture
def server(kb):
    return McpServer(kb)


# ---------- 握手 ----------


def test_initialize_returns_protocol_version(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    result = resp["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["serverInfo"]["name"]
    assert "tools" in result["capabilities"]


def test_ping(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert resp["result"] == {}


# ---------- 工具列表 ----------


def test_tools_list_exposes_three_tools(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})

    tools = resp["result"]["tools"]
    names = {t["function"]["name"] for t in tools}
    assert names == {"list_documents", "search_kb", "read_chunk"}


def test_tools_list_schema_is_valid(server):
    """每个工具都要有 name / description / parameters，客户端才能正确渲染。"""
    resp = server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/list"})

    for tool in resp["result"]["tools"]:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert fn["name"]
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"


def test_tools_list_matches_agent_tools(server):
    """MCP 暴露的工具必须和 Agent 用的是同一份定义，避免两边漂移。"""
    from app.agent.tools import TOOL_SCHEMAS

    resp = server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/list"})
    assert resp["result"]["tools"] == TOOL_SCHEMAS


# ---------- 工具调用 ----------


def test_call_list_documents(server):
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "list_documents", "arguments": {}},
        }
    )

    payload = json.loads(resp["result"]["content"][0]["text"])
    assert len(payload["items"]) == 2
    assert resp["result"]["isError"] is False


def test_call_search_kb(server):
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "search_kb", "arguments": {"query": "配置 6145", "k": 3}},
        }
    )

    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["items"], "应该有检索结果"
    assert resp["result"]["isError"] is False


def test_call_search_kb_with_bad_arguments(server):
    """工具层的校验错误要转成 isError=True 加文本说明，而不是抛 JSON-RPC 错误。"""
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "search_kb", "arguments": {"query": ""}},
        }
    )

    payload = json.loads(resp["result"]["content"][0]["text"])
    assert "error" in payload
    assert resp["result"]["isError"] is True


def test_call_unknown_tool(server):
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "no_such_tool", "arguments": {}},
        }
    )

    payload = json.loads(resp["result"]["content"][0]["text"])
    assert "error" in payload
    assert resp["result"]["isError"] is True


def test_call_without_tool_name_is_rpc_error(server):
    """缺 name 属于协议层错误，返回 JSON-RPC error 而不是工具错误。"""
    resp = server.handle({"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {}})

    assert resp["error"]["code"] == -32603


# ---------- 协议边界 ----------


def test_unknown_method_returns_method_not_found(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 11, "method": "no/such"})

    assert resp["error"]["code"] == -32601


def test_notification_gets_no_response(server):
    """通知类消息（没有 id）不应产生响应，否则客户端会报协议错误。"""
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_notification_for_unknown_method_is_silent(server):
    """即使未知方法，只要是通知就不响应。"""
    resp = server.handle({"jsonrpc": "2.0", "method": "no/such"})
    assert resp is None


# ---------- serve 的 stdio 行为 ----------


def test_serve_handles_multiple_lines(kb):
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    ]
    stdin = io.StringIO("\n".join(lines) + "\n")
    stdout = io.StringIO()

    serve(kb, stdin=stdin, stdout=stdout)

    out = [json.loads(x) for x in stdout.getvalue().strip().split("\n") if x]
    assert len(out) == 2
    assert out[0]["id"] == 1
    assert out[1]["id"] == 2


def test_serve_skips_blank_lines(kb):
    stdin = io.StringIO("\n\n  \n" + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n")
    stdout = io.StringIO()

    serve(kb, stdin=stdin, stdout=stdout)

    out = [json.loads(x) for x in stdout.getvalue().strip().split("\n") if x]
    assert len(out) == 1 and out[0]["id"] == 1


def test_serve_reports_parse_error(kb):
    """非法 JSON 要返回 -32700 解析错误，而不是崩溃。"""
    stdin = io.StringIO("{不是合法 json\n")
    stdout = io.StringIO()

    serve(kb, stdin=stdin, stdout=stdout)

    resp = json.loads(stdout.getvalue().strip())
    assert resp["error"]["code"] == -32700
    assert resp["id"] is None


def test_serve_continues_after_parse_error(kb):
    """一次解析失败不能中断后续请求。"""
    stdin = io.StringIO("bad json\n" + json.dumps({"jsonrpc": "2.0", "id": 9, "method": "ping"}) + "\n")
    stdout = io.StringIO()

    serve(kb, stdin=stdin, stdout=stdout)

    lines = [x for x in stdout.getvalue().strip().split("\n") if x]
    assert len(lines) == 2
    assert json.loads(lines[1])["id"] == 9
