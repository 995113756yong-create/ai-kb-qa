"""句子级溯源：把回答拆成句子，用程序（而不是模型自述）标注每句的来源。

为什么用程序标注：
模型自我声明不可验证。程序按「有没有合法引用」切句分类，结果确定、可测试、
可度量，grounded_ratio 可以直接写进评测报告。

三类句子：
- kb       带合法引用编号的句子（来自知识库）
- general  无引用、非声明、有实际内容的句子（一般知识）
- neutral  空行、标点、小标题、来源声明、安全提醒（不参与比例计算）
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------- 切句 ----------

# 一个 span = 非终止符的字符 + （终止符串 + 紧跟其后的引用标记 | 换行 | 结尾）
# 英文句点 "." 不作为终止符，避免把 2.5 这类小数切开。
SPAN_RE = re.compile(r"[^。！？!?；;\n]*(?:[。！？!?；;]+(?:[ \t]*\[\d+\])*|\n|$)")

# ---------- 分类 ----------

CIT_RE = re.compile(r"\[(\d+)\]")
LIST_MARK_RE = re.compile(r"^\s*(?:[-*•]|\d+[.、)）]|#+)\s*")
DISCLAIMER_RE = re.compile(
    r"(知识库|文档)中?(暂无|没有|未找到|未提及|未覆盖)|一般知识|仅供参考|请咨询|咨询(医生|专业)|及时就医"
)

# ---------- 数字一致性 ----------

NUM_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Segment:
    text: str                 # 原文片段，含 [n] 标记；所有 segment 的 text 按顺序拼接必须严格等于 answer
    kind: str                 # "kb" | "general" | "neutral"
    citations: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class Attribution:
    segments: List[Segment] = field(default_factory=list)
    kb_count: int = 0
    general_count: int = 0
    grounded_ratio: Optional[float] = None  # kb / (kb + general)，两者都为 0 时为 None
    numeric_warnings: int = 0
    grounded: bool = True  # kb_count > 0 且 general_count == 0 且 numeric_warnings == 0


def split_spans(answer: str) -> List[str]:
    """无损切句：所有 span 按顺序拼接严格等于原文。"""
    return [m.group(0) for m in SPAN_RE.finditer(answer) if m.group(0)]


def _core_len(body: str) -> int:
    core = re.sub(r"[\W_]", "", body)  # Python 的 \w 包含中文字符
    return len(core)


def classify_span(span: str, valid_ids=None) -> tuple:
    """返回 (kind, citations, body)。

    valid_ids 不为 None 时 citations 只保留存在的编号（在分类前过滤，
    引用编号全部无效的句子不再判成 kb）。
    判定顺序：先看引用（有合法引用即 kb），再做短文本/标题/声明的 neutral
    判定——一句很短但带合法引用的话（如「是 3 次 [1]」）仍是知识库句。
    """
    citations = [int(n) for n in CIT_RE.findall(span)]
    if valid_ids is not None:
        citations = [c for c in citations if c in valid_ids]
    body = LIST_MARK_RE.sub("", CIT_RE.sub("", span)).strip()
    if citations:
        kind = "kb"
    elif _core_len(body) < 6:
        kind = "neutral"            # 空行、标点、很短的连接语
    elif body.endswith(("：", ":")):
        kind = "neutral"            # 小标题
    elif DISCLAIMER_RE.search(body):
        kind = "neutral"            # 来源声明、安全提醒
    else:
        kind = "general"
    return kind, citations, body


def attribute(answer: str, sources: List[dict], question: str = "") -> Attribution:
    """对整段回答做句子级溯源。sources 是 final 事件里的出处列表。"""
    valid_ids = {s["index"] for s in sources} if sources else set()
    by_index: Dict[int, dict] = {s["index"]: s for s in (sources or [])}

    segments: List[Segment] = []
    for span in split_spans(answer):
        kind, citations, body = classify_span(span, valid_ids)
        warnings: List[str] = []
        if kind == "kb":
            warnings = _check_numbers(body, citations, by_index, question)
        segments.append(
            Segment(text=span, kind=kind, citations=citations, warnings=warnings)
        )

    kb_count = sum(1 for s in segments if s.kind == "kb")
    general_count = sum(1 for s in segments if s.kind == "general")
    numeric_warnings = sum(len(s.warnings) for s in segments)

    if kb_count + general_count == 0:
        ratio: Optional[float] = None
    else:
        ratio = kb_count / (kb_count + general_count)

    return Attribution(
        segments=segments,
        kb_count=kb_count,
        general_count=general_count,
        grounded_ratio=ratio,
        numeric_warnings=numeric_warnings,
        grounded=kb_count > 0 and general_count == 0 and numeric_warnings == 0,
    )


def _check_numbers(
    body: str,
    citations: List[int],
    by_index: Dict[int, dict],
    question: str,
) -> List[str]:
    """数字一致性检查：kb 句子里的数字必须出现在它引用的片段原文或问题里。

    只检查当前句子引用的那些片段，而不是全部证据——
    这样能发现「引用了 A 片段、数字却来自别处」的错误引用。
    推算类数字会被告警，prompt 要求推算写在不带引用的句子里。
    """
    allowed = "\n".join(
        (by_index.get(c) or {}).get("content") or (by_index.get(c) or {}).get("snippet") or ""
        for c in citations
    )
    allowed += "\n" + (question or "")

    warnings: List[str] = []
    for n in dict.fromkeys(NUM_RE.findall(body)):
        if not re.search(rf"(?<![\d.]){re.escape(n)}(?!\d)", allowed):
            warnings.append(f"数字 {n} 未出现在引用片段中，可能是推算或编造")
    return warnings
