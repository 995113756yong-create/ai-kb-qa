"""语言检测与跨语言检索支持。

问题：用户用英文提问，但知识库是中文语料时，向量检索匹配不上，
回答质量骤降（实测通过率从 100% 掉到 69.2%）。

做法：只翻译「查询」，不翻译语料。
    英文提问 + 中文语料 → 把问题翻成中文去检索 → 用原文片段 + 英文问题作答
优势：语料零迁移成本，检索走语料的原生语言，准确率不受影响。

设计原则：
- 只在「提问语言 ≠ 语料语言」时才翻译，同语言不付额外代价
- 翻译失败时回落到原问题，不阻塞请求
- 判断语料语言用采样，不遍历全部文档
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# 中日韩统一表意文字
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
# 拉丁字母
_LATIN_RE = re.compile(r"[A-Za-z]")

# 判定语言所需的最少有效字符数；太短的文本不可靠
_MIN_SAMPLE_CHARS = 10
# 采样上限：只看前若干片段，大知识库也不至于遍历全部
_SAMPLE_LIMIT = 30
# 一种文字占比超过这个阈值就判定为该语言
_DOMINANT_RATIO = 0.6


def detect_text_language(text: str) -> Optional[str]:
    """检测单段文本的语言，只区分 zh / en，无法判断返回 None。

    中文按汉字计数，英文按拉丁字母计数，取占比高者。
    数字、标点、空白不参与判断。
    """
    if not text:
        return None
    sample = text[:_MIN_SAMPLE_CHARS * 200]
    cjk = len(_CJK_RE.findall(sample))
    latin = len(_LATIN_RE.findall(sample))
    total = cjk + latin
    if total < _MIN_SAMPLE_CHARS:
        return None
    if cjk / total >= _DOMINANT_RATIO:
        return "zh"
    if latin / total >= _DOMINANT_RATIO:
        return "en"
    return None


def detect_corpus_language(texts: Iterable[str]) -> Optional[str]:
    """从若干文档片段检测知识库的主要语言。

    取所有片段的字符统计总和，而不是逐片段投票 ——
    这样短片段（如纯数字表格）不会因为误判而拉偏结果。
    """
    cjk = 0
    latin = 0
    seen = 0
    for t in texts:
        if not t:
            continue
        cjk += len(_CJK_RE.findall(t))
        latin += len(_LATIN_RE.findall(t))
        seen += 1
        if seen >= _SAMPLE_LIMIT:
            break

    total = cjk + latin
    if total < _MIN_SAMPLE_CHARS:
        return None
    if cjk / total >= _DOMINANT_RATIO:
        return "zh"
    if latin / total >= _DOMINANT_RATIO:
        return "en"
    return None


def should_translate_query(question_lang: Optional[str], corpus_lang: Optional[str]) -> bool:
    """是否需要把查询翻译成语料语言。

    只在两边都判定成功且不一致时才翻译。
    任一未知（如纯数字问题、空知识库）都不翻译，避免误伤。
    """
    if not question_lang or not corpus_lang:
        return False
    return question_lang != corpus_lang


_LANG_NAME = {"zh": "中文", "en": "English"}

TRANSLATE_PROMPT = (
    "把下面的问题翻译成{target}。只输出译文，不要解释、不要加引号、不要保留原文。\n"
    "要求：\n"
    "- 保留专有名词、产品名、缩写、数字和单位原样（如 RPE、1RM、GPT-4、30 元）\n"
    "- 保留原有的引号、括号等标点结构\n"
    "- 如果原文已经是{target}，原样输出\n\n"
    "问题：{question}"
)


def build_translate_prompt(question: str, target_lang: str) -> str:
    return TRANSLATE_PROMPT.format(
        target=_LANG_NAME.get(target_lang, target_lang),
        question=question,
    )


def clean_translation(raw: str, original: str) -> str:
    """清理模型返回的译文。

    模型常见的多余输出：包裹的引号、前缀「译文：」、多行解释。
    清理后如果为空或与原文相同，调用方应回落到原文。
    """
    if not raw:
        return original
    text = raw.strip()

    # 去掉常见的说明性前缀
    for prefix in ("译文：", "译文:", "翻译：", "翻译:", "Translation:", "translated:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()

    # 去掉整体包裹的引号
    pairs = [('"', '"'), ("'", "'"), ("「", "」"), ("“", "”"), ("《", "》")]
    for left, right in pairs:
        if len(text) >= 2 and text.startswith(left) and text.endswith(right):
            text = text[1:-1].strip()

    # 只取第一段非空行，避免模型附加解释
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return original
    text = lines[0]

    # 明显异常（太长）时放弃
    if len(text) > max(200, len(original) * 4):
        return original
    return text or original
