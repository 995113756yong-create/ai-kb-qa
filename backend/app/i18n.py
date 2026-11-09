"""后端文案国际化。

错误信息按请求语言返回。语言来源优先 Accept-Language，其次 query/header 覆盖，
最后回落到默认中文。

设计要点：
- 只翻译「用户可见的错误信息」，日志仍用中文（便于内部排查）
- 翻译缺失时回落到中文，不让界面出现空串或 key
- 不引入 HTTP 框架依赖，纯函数 + ContextVar，中间件里设置当前语言
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Any

DEFAULT_LANG = "zh"
SUPPORTED = ("zh", "en")

# 当前请求语言。用 ContextVar 而不是全局变量，避免并发请求串语言。
_current_lang: ContextVar[str] = ContextVar("current_lang", default=DEFAULT_LANG)

# 语言键 -> {lang: 文案}
MESSAGES: dict[str, dict[str, str]] = {
    # --- 专家 ---
    "agent.not_found": {
        "zh": "专家不存在",
        "en": "Expert not found",
    },
    "agent.not_found_id": {
        "zh": "专家不存在：{agent_id}",
        "en": "Expert not found: {agent_id}",
    },
    "agent.not_deletable": {
        "zh": "专家不存在或不可删除：{agent_id}",
        "en": "Expert not found or cannot be deleted: {agent_id}",
    },
    "agent.name_required": {
        "zh": "专家名称不能为空",
        "en": "Expert name is required",
    },
    "agent.name_too_long": {
        "zh": "专家名称不能超过 {max_len} 字",
        "en": "Expert name must not exceed {max_len} characters",
    },
    "agent.model_invalid": {
        "zh": "模型名不合法",
        "en": "Invalid model name",
    },
    "agent.answer_mode_invalid": {
        "zh": "answer_mode 必须是 {modes} 之一",
        "en": "answer_mode must be one of {modes}",
    },
    "agent.starters_too_many": {
        "zh": "starter_questions 最多 4 条",
        "en": "At most 4 starter questions are allowed",
    },
    "agent.id_invalid": {
        "zh": "agent_id 只能包含小写字母、数字和连字符，最长 32 位",
        "en": "agent_id may only contain lowercase letters, digits and hyphens, max 32 chars",
    },
    "agent.id_reserved": {
        "zh": "default 是保留 ID，不能用于新建专家",
        "en": "'default' is a reserved ID and cannot be used for a new expert",
    },
    "agent.id_exists": {
        "zh": "agent_id 已存在：{agent_id}",
        "en": "agent_id already exists: {agent_id}",
    },
    # --- 文档 ---
    "doc.empty": {
        "zh": "文档内容为空，无法建立索引",
        "en": "Document is empty and cannot be indexed",
    },
    "doc.vector_mismatch": {
        "zh": "向量数量与片段数量不一致，无法建立索引",
        "en": "Vector count does not match chunk count; cannot index",
    },
    "doc.id_invalid": {
        "zh": "文档 ID 格式不正确",
        "en": "Invalid document ID format",
    },
    "doc.doc_id_invalid": {
        "zh": "doc_id 格式不合法",
        "en": "Invalid doc_id format",
    },
    "doc.not_found": {
        "zh": "文档不存在",
        "en": "Document not found",
    },
    "doc.no_chunks": {
        "zh": "文档没有可用的片段",
        "en": "Document has no available chunks",
    },
    "doc.chunk_not_found": {
        "zh": "片段不存在",
        "en": "Chunk not found",
    },
    "doc.process_failed": {
        "zh": "文档处理失败：{err}",
        "en": "Document processing failed: {err}",
    },
    "doc.file_type_unsupported": {
        "zh": "不支持的文件类型，仅支持 {allowed}",
        "en": "Unsupported file type; only {allowed} are supported",
    },
    "doc.file_too_large": {
        "zh": "文件超过 {max_mb}MB 上限",
        "en": "File exceeds the {max_mb}MB limit",
    },
    "doc.file_empty": {
        "zh": "文件为空",
        "en": "File is empty",
    },
    # --- 通用 ---
    "kb.not_ready": {
        "zh": "知识库未就绪",
        "en": "Knowledge base is not ready",
    },
    "kb.missing_key": {
        "zh": "服务未配置 OPENAI_API_KEY，暂时无法上传和问答",
        "en": "OPENAI_API_KEY is not configured; upload and Q&A are unavailable",
    },
    "question.empty": {
        "zh": "问题不能为空",
        "en": "Question must not be empty",
    },
    "qa.failed": {
        "zh": "问答失败：{err}",
        "en": "Q&A failed: {err}",
    },
    # --- 鉴权与限流 ---
    "auth.admin_required": {
        "zh": "需要管理员口令",
        "en": "Admin token required",
    },
    "auth.admin_invalid": {
        "zh": "管理员口令不正确",
        "en": "Invalid admin token",
    },
    "rate.limited": {
        "zh": "请求过于频繁，请稍后再试",
        "en": "Too many requests; please try again later",
    },
    # --- Agent 运行时 ---
    "runtime.llm_failed": {
        "zh": "大模型调用失败：{err}",
        "en": "Model call failed: {err}",
    },
    "runtime.answer_mode_invalid": {
        "zh": "answer_mode 必须是 {modes} 之一，收到 {got}",
        "en": "answer_mode must be one of {modes}, got {got}",
    },
    "runtime.tool_args_invalid_json": {
        "zh": '参数不是合法 JSON（{err}）。请传一个 JSON 对象，例如 {{"query": "关键词"}}',
        "en": 'Arguments are not valid JSON ({err}). Pass a JSON object, e.g. {{"query": "keyword"}}',
    },
    "runtime.tool_args_not_object": {
        "zh": '参数必须是 JSON 对象，例如 {{"query": "关键词"}}',
        "en": 'Arguments must be a JSON object, e.g. {{"query": "keyword"}}',
    },
    # --- MCP ---
    "mcp.name_required": {
        "zh": "缺少 name 参数",
        "en": "Missing 'name' parameter",
    },
}


def normalize_lang(raw: str | None) -> str:
    """把 Accept-Language 归一化成 zh / en。

    "en-US,en;q=0.9,zh-CN;q=0.8" -> "en"
    "zh-CN" -> "zh"
    无法识别 -> 默认中文
    """
    if not raw:
        return DEFAULT_LANG
    # 取第一个语言标签（忽略 q 权重，浏览器已按偏好排序）
    first = raw.split(",")[0].strip().lower()
    code = re.split(r"[-_]", first)[0]
    return code if code in SUPPORTED else DEFAULT_LANG


def set_lang(lang: str) -> object:
    """设置当前请求语言，返回可用于 reset 的 token。"""
    return _current_lang.set(lang if lang in SUPPORTED else DEFAULT_LANG)


def reset_lang(token: object) -> None:
    """恢复设置前的语言（中间件 finally 里调用，避免跨请求泄漏）。"""
    try:
        _current_lang.reset(token)  # type: ignore[arg-type]
    except (ValueError, RuntimeError):
        # token 来自其他 context 时忽略，回落到默认语言
        _current_lang.set(DEFAULT_LANG)


def get_lang() -> str:
    return _current_lang.get()


def tr(key: str, lang: str | None = None, **vars: Any) -> str:
    """取当前语言的文案，并替换 {name} 占位符。

    翻译缺失时回落中文；中文也缺失时返回 key 本身（便于发现遗漏）。
    """
    target = lang or get_lang()
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(target) or entry.get(DEFAULT_LANG) or key
    if vars:
        for k, v in vars.items():
            text = text.replace("{%s}" % k, str(v))
    return text


def all_keys() -> list[str]:
    return sorted(MESSAGES.keys())
