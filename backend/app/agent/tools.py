"""工具定义（OpenAI tools 格式）与执行。所有错误都转成 {"error": ...} 交回模型自行修正。"""
import json
from typing import Any, Callable, Dict, List

from app.config import AGENT_SEARCH_K
from app.document import KnowledgeBase
from app.agent.evidence import EvidenceRegistry

MAX_RESULT_CHARS = 4000
SNIPPET_CHARS = 600

TOOL_SCHEMAS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "列出知识库里所有文档的 ID、文件名和片段数。当你不确定知识库里有哪些文档，"
            "或者需要确认某份文档是否存在时使用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "在知识库中按语义检索相关片段。回答任何需要事实依据的问题前都应该先调用它。"
            "涉及多个对象、需要对比，或第一次检索结果不相关时，换关键词多次调用；"
            "已经知道信息在哪份文档时可用 doc_id 限定范围。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词或一句话问题，1 到 200 字。",
                    },
                    "k": {
                        "type": "integer",
                        "description": "返回片段数，1 到 8，默认 5。",
                    },
                    "doc_id": {
                        "type": "string",
                        "description": "可选，只在这份文档内检索；不填表示全库检索。",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_chunk",
            "description": "读取某条证据片段前后相邻的片段，用于补全上下文（例如表格跨片段、段落被切断）。"
            "参数是证据编号，例如 E3，只能使用检索结果里出现过的编号。",
            "parameters": {
                "type": "object",
                "properties": {
                    "evidence_id": {
                        "type": "string",
                        "description": "检索结果中给出的证据编号，例如 E3。",
                    },
                    "window": {
                        "type": "integer",
                        "description": "向前后各取几个片段，0 到 2，默认 1。",
                    },
                },
                "required": ["evidence_id"],
            },
        },
    },
]


def _truncate(text: str, limit: int = SNIPPET_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _parse_args(raw: str) -> Dict[str, Any]:
    """模型给的 arguments 是字符串，可能是空串或非法 JSON，这里统一容错。"""
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"参数不是合法 JSON（{e}）。请传一个 JSON 对象，例如 {{\"query\": \"关键词\"}}") from e
    if not isinstance(parsed, dict):
        raise ValueError("参数必须是 JSON 对象，例如 {\"query\": \"关键词\"}")
    return parsed


def _format_evidence(evidence, text: str) -> str:
    meta = evidence.document.metadata or {}
    source = meta.get("source") or "未知文档"
    page = meta.get("page")
    location = f"{source} 第{page}页" if page else source
    return f"[{evidence.evidence_id}] {location}\n{_truncate(text)}"


def list_documents(kb: KnowledgeBase, registry: EvidenceRegistry, args: Dict[str, Any]) -> dict:
    docs = kb.list_documents()
    if not docs:
        return {"items": [], "message": "知识库为空，没有任何文档。"}
    return {
        "items": [
            {"doc_id": d["doc_id"], "filename": d["filename"], "chunks": d["chunks"]}
            for d in docs
        ]
    }


def search_kb(
    kb: KnowledgeBase,
    registry: EvidenceRegistry,
    args: Dict[str, Any],
    default_k: int = AGENT_SEARCH_K,
) -> dict:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "query 不能为空。请传入检索关键词，例如 {\"query\": \"报销流程\"}"}
    if len(query) > 200:
        return {"error": "query 不能超过 200 字，请缩短后重试"}

    k = _clamp(args.get("k", default_k), 1, 8, default_k)
    doc_id = args.get("doc_id")
    if doc_id is not None and not isinstance(doc_id, str):
        return {"error": "doc_id 必须是字符串，例如 \"3f2a…\"；不确定时不要传这个参数"}

    hits = kb.search_with_scores(query, k=k, doc_id=doc_id or None)
    if not hits:
        return {"items": [], "message": f"没有检索到与「{query}」相关的内容，可以换关键词再试"}

    evidences = registry.register_many([doc for doc, _ in hits])
    scores = [round(float(score), 4) for _, score in hits]
    return {
        "items": [
            {
                "evidence_id": evidence.evidence_id,
                "text": _format_evidence(evidence, evidence.document.page_content),
            }
            for evidence in evidences
        ],
        "scores": scores,
    }


def read_chunk(kb: KnowledgeBase, registry: EvidenceRegistry, args: Dict[str, Any]) -> dict:
    evidence_id = str(args.get("evidence_id", "")).strip()
    if not evidence_id:
        return {"error": "evidence_id 不能为空，例如 \"E3\"，编号来自之前检索结果的输出"}
    evidence = registry.get(evidence_id)
    if evidence is None:
        known = [e.evidence_id for e in registry.all()]
        return {
            "error": f"证据编号 {evidence_id} 不存在。当前可用编号：{', '.join(known) or '无'}",
        }

    window = _clamp(args.get("window", 1), 0, 2, 1)
    metadata = evidence.document.metadata or {}
    chunk_id = metadata.get("chunk_id")
    if not chunk_id:
        return {"items": [_format_evidence(evidence, evidence.document.page_content)]}

    neighbors = kb.get_neighbors(str(chunk_id), window=window)
    if not neighbors:
        return {"items": [_format_evidence(evidence, evidence.document.page_content)]}

    evidences = registry.register_many(neighbors)
    return {
        "items": [
            {
                "evidence_id": item.evidence_id,
                "text": _format_evidence(item, item.document.page_content),
            }
            for item in evidences
        ]
    }


_HANDLERS: Dict[str, Callable[[KnowledgeBase, EvidenceRegistry, Dict[str, Any]], dict]] = {
    "list_documents": list_documents,
    "search_kb": search_kb,
    "read_chunk": read_chunk,
}


def execute_tool(
    name: str,
    raw_arguments: str,
    kb: KnowledgeBase,
    registry: EvidenceRegistry,
    search_k: int = AGENT_SEARCH_K,
) -> dict:
    """执行工具；参数解析 / 校验 / 内部异常都转成 {"error": ...}，不向上抛。"""
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"没有名为 {name} 的工具。可用工具：{', '.join(_HANDLERS)}"}
    try:
        args = _parse_args(raw_arguments)
        if name == "search_kb":
            result = handler(kb, registry, args, default_k=search_k)
        else:
            result = handler(kb, registry, args)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:  # 检索失败等内部异常也让模型知道，而不是中断整轮对话
        return {"error": f"工具执行失败：{e}"}

    return result


def to_text(result: dict) -> str:
    """把工具结果序列化成给模型的文本，超长截断并注明。"""
    text = json.dumps(result, ensure_ascii=False)
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[:MAX_RESULT_CHARS] + "…（已截断）"


def summarize(result: dict) -> str:
    """给前端时间线用的短摘要，例如“命中 5 条：A.pdf 第2页…”。"""
    if "error" in result:
        return str(result["error"])
    items = result.get("items")
    if items is None:
        return result.get("message", "完成")
    if not items:
        return result.get("message", "无结果")

    first = items[0]
    if isinstance(first, dict) and "filename" in first:
        return f"共 {len(items)} 份文档，例如 {first['filename']}"
    text = str(first.get("text", "")).replace("\n", " ")
    head = text[:60]
    return f"命中 {len(items)} 条：{head}…" if len(text) > 60 else f"命中 {len(items)} 条：{head}"
