"""把知识库的三个工具暴露成标准 MCP Server（stdio 传输）。

为什么要做这个：
工具层原本绑死在 agent/tools.py 里，只能被本项目的 Agent 用。
抽象成 MCP Server 后，任何支持 MCP 的客户端（Claude Desktop、Cursor、
其他 Agent 框架）都能直接接入这个知识库，工具实现只写一份。

为什么不用官方 mcp SDK：
RPC 部分只有百来行，用标准库实现可以零新增依赖，
也便于讲清协议细节——面试时能说「MCP 就是 JSON-RPC 2.0 over stdio，
三个方法 initialize / tools/list / tools/call」。

启动方式：
    python -m app.mcp_server

协议：
    stdin 每行一个 JSON-RPC 请求，stdout 每行一个响应。
    stdout 只能输出协议数据，日志一律走 stderr。
"""
import json
import sys
from typing import Any, Dict, List

from app.document import KnowledgeBase, get_embeddings
from app.agent.evidence import EvidenceRegistry
from app.agent.tools import TOOL_SCHEMAS, execute_tool

SERVER_NAME = "kb-qa"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"


class McpServer:
    """极简 MCP Server：只实现知识库问答需要的三个方法。"""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        # MCP 是无状态的单轮调用，每次请求用独立的证据登记表
        self.registry = EvidenceRegistry()

    # ---------- 协议分发 ----------

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any] | None:
        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params") or {}

        # 通知类消息没有 id，不需要响应
        is_notification = req_id is None

        try:
            if method == "initialize":
                result = self._initialize()
            elif method == "tools/list":
                result = self._tools_list()
            elif method == "tools/call":
                result = self._tools_call(params)
            elif method == "ping":
                result = {}
            else:
                # 按 JSON-RPC 2.0：通知（无 id）永远不能收到响应，
                # 哪怕方法不存在。只有带 id 的请求才回 method not found。
                if is_notification:
                    return None
                return self._error(req_id, -32601, f"未知方法: {method}")
        except Exception as e:  # 任何内部异常都转成 JSON-RPC 错误
            if is_notification:
                return None
            return self._error(req_id, -32603, f"内部错误: {type(e).__name__}: {e}")

        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _initialize(self) -> Dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    def _tools_list(self) -> Dict[str, Any]:
        # 复用一份定义，避免 Agent 和 MCP 两边的工具描述漂移
        return {"tools": TOOL_SCHEMAS}

    def _tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}

        if not name:
            raise ValueError("缺少 name 参数")

        result = execute_tool(name, json.dumps(arguments, ensure_ascii=False), self.kb, self.registry)

        # MCP 要求返回 content 数组；把结构化结果序列化进 text 字段
        text = json.dumps(result, ensure_ascii=False)
        return {
            "content": [{"type": "text", "text": text}],
            "isError": "error" in result,
        }

    @staticmethod
    def _error(req_id, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def serve(kb: KnowledgeBase, stdin=None, stdout=None) -> None:
    """按行读写 JSON-RPC，直到 stdin 关闭。"""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = McpServer(kb)

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            # 连请求都解析不了，没有 id 可回，用 null
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"解析失败: {e}"}}
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            stdout.flush()
            continue

        response = server.handle(request)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()


def main() -> int:
    """命令行入口：从配置加载知识库后进入 stdio 循环。"""
    import os

    from app import config

    index_dir = config.FAISS_DIR
    if not os.path.exists(os.path.join(index_dir, "index.faiss")):
        print(f"知识库为空或不存在: {index_dir}", file=sys.stderr)
        print("请先通过 API 上传文档，或设置 FAISS_DIR 指向已有索引", file=sys.stderr)

    kb = KnowledgeBase(index_dir, get_embeddings())
    print(
        f"MCP Server 启动，知识库 {len(kb.list_documents())} 份文档，"
        f"{getattr(kb._store.index, 'ntotal', 0) if kb._store else 0} 个片段",
        file=sys.stderr,
    )
    serve(kb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
