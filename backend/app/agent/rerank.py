"""Rerank：用 LLM 对检索候选做二次排序，提升 Top-K 的排序精度。

为什么需要：
混合检索（向量 + BM25）解决的是"召回"——结果有没有被捞回来；
但召回的候选里，真正最相关的那条不一定排在最前面，模型会优先看
排名靠前的证据来组织回答，排序不准会导致回答引用了次相关的证据。

做法：
不引入 cross-encoder 模型（没有现成的中文 cross-encoder 权重，
自己训练成本太高），改用对已经在用的 LLM 做一次"打分"调用：
把查询和候选片段列出来，让模型给每个片段打 0-10 的相关度分，
按分数重排。这是「LLM-as-reranker」的轻量实现，不额外引入依赖。

代价：多一次 LLM 调用，所以只在候选数 > 1 时才有意义；
候选数很少时（比如只检索到 1 条）直接跳过。
"""
import json
import logging
import re
from typing import List, Tuple

from langchain_core.documents import Document

from app.agent.llm import AgentLLM

logger = logging.getLogger(__name__)

# 候选数低于这个数，排序意义不大，跳过 rerank 省一次 LLM 调用
MIN_CANDIDATES_FOR_RERANK = 2

# 送进 rerank 的片段截断长度：只需要模型判断相关性，不需要完整正文
RERANK_SNIPPET_CHARS = 300

RERANK_PROMPT = """你是一个相关性评分助手。给定一个查询和多个候选文本片段，
给每个片段打 0 到 10 的相关度分数：10 表示直接回答了查询，0 表示完全无关。

只输出一个 JSON 数组，数组长度必须等于片段数，每项是对应片段的分数（整数）。
不要输出任何解释、前缀或 markdown 代码块标记。

查询：{query}

片段：
{snippets}"""

_JSON_ARRAY_RE = re.compile(r"\[[\d,\s]*\]")


def _format_snippets(docs: List[Document]) -> str:
    lines = []
    for i, doc in enumerate(docs, start=1):
        text = doc.page_content
        if len(text) > RERANK_SNIPPET_CHARS:
            text = text[:RERANK_SNIPPET_CHARS] + "…"
        lines.append(f"[{i}] {text}")
    return "\n\n".join(lines)


def _parse_scores(raw: str, expected_len: int) -> List[float]:
    """解析模型打分；长度不对或解析失败时返回 None 风格的空列表，调用方据此回退原序。"""
    if not raw or not raw.strip():
        return []

    match = _JSON_ARRAY_RE.search(raw)
    candidate = match.group(0) if match else raw.strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list) or len(parsed) != expected_len:
        return []

    scores = []
    for item in parsed:
        try:
            scores.append(float(item))
        except (TypeError, ValueError):
            return []
    return scores


def rerank(llm: AgentLLM, query: str, docs: List[Document]) -> List[Document]:
    """按相关度重新排序；任何失败都原样返回输入顺序，绝不让 rerank 变成故障点。"""
    if len(docs) < MIN_CANDIDATES_FOR_RERANK:
        return docs

    prompt = RERANK_PROMPT.format(query=query, snippets=_format_snippets(docs))
    try:
        turn = llm.chat([{"role": "user", "content": prompt}])
    except Exception as e:
        logger.warning("rerank 调用失败，保留原排序：%s", e)
        return docs

    scores = _parse_scores(turn.content, len(docs))
    if not scores:
        logger.warning("rerank 输出解析失败，保留原排序：%r", turn.content[:200])
        return docs

    paired: List[Tuple[Document, float]] = list(zip(docs, scores))
    # 用 stable sort：分数相同的候选保留原有的检索排名顺序
    paired.sort(key=lambda pair: pair[1], reverse=True)
    return [doc for doc, _ in paired]
