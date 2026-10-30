"""查询改写：复合问题拆解成独立子问题，预先各自检索，保证证据不遗漏。

为什么需要：
系统提示词里写了"涉及多个对象时分别检索"，但这完全依赖模型的自觉性——
提示词只是建议，小模型经常偷懒，一次检索就直接回答，漏掉其中一个对象。
"产品A和产品B的月费分别是多少"这类问题，模型可能只查了产品A就作答。

做法：
ReAct 循环开始前，先用启发式规则判断问题是否"看起来"是复合问题，
命中时才调用一次 LLM 做真正的拆解（避免给每个简单问题都多花一次 token）。
拆出的每个子问题直接调用检索并把证据预先登记进 registry，
不经过模型的工具调用流程——这样无论模型后续是否记得分头查，
回答阶段用到的证据库里已经保底覆盖了所有子问题。
"""
import json
import logging
import re
from typing import List

from app.agent.llm import AgentLLM

logger = logging.getLogger(__name__)

MAX_SUB_QUERIES = 4

# 启发式触发词：避免对每个简单问题都多调用一次 LLM 做拆解判断。
# 只在"看起来像复合问题"时才真正调用 LLM 确认与拆解。
_MULTI_ASK_MARKERS = ("分别", "各自", "各是", "都是什么")
_COMPARE_CONJUNCTIONS = ("和", "与", "跟", "及")
_COMPARE_CUES = ("对比", "比较", "哪个", "哪一个", "更", "区别", "差异", "哪些")

DECOMPOSE_PROMPT = """你是一个问题拆解助手。判断用户问题是否包含多个独立的子问题——
比如同时问多个对象的同一类信息、需要分别查不同事实再汇总比较的问题。

规则：
1. 单一问题：直接返回只含原问题的 JSON 数组，例如 ["原问题"]
2. 复合问题：拆成互相独立、每个都能单独检索回答的子问题，每个子问题必须是
   完整的问句，不能依赖其他子问题的答案（不能写"它的"这种指代）。
3. 最多拆成 4 个子问题。
4. 只输出 JSON 数组，不要输出任何解释、前缀或 markdown 代码块标记。

示例：
问题：产品A和产品B的月费分别是多少？
输出：["产品A的月费是多少？", "产品B的月费是多少？"]

问题：配置6145是谁负责的？
输出：["配置6145是谁负责的？"]

问题：如果团队有10个人，产品A需要额外付多少钱？
输出：["如果团队有10个人，产品A需要额外付多少钱？"]"""

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def should_attempt_decompose(question: str) -> bool:
    """零成本的启发式预判：问题"看起来"像复合问题才值得花一次 LLM 调用确认。

    规则宽松但不滥用：命中"分别/各自"这类强信号词，或同时出现
    并列连词（和/与/跟/及）与比较类线索词（对比/哪个/更…）。
    """
    if any(marker in question for marker in _MULTI_ASK_MARKERS):
        return True
    has_conj = any(c in question for c in _COMPARE_CONJUNCTIONS)
    has_cue = any(c in question for c in _COMPARE_CUES)
    return has_conj and has_cue


def decompose_question(llm: AgentLLM, question: str) -> List[str]:
    """返回子问题列表，至少 1 个。任何解析失败都退化为 [question] 本身。

    不在这里做 should_attempt_decompose 判断，调用方决定是否要先过一遍启发式。
    """
    messages = [
        {"role": "system", "content": DECOMPOSE_PROMPT},
        {"role": "user", "content": question},
    ]
    try:
        turn = llm.chat(messages)
    except Exception as e:
        logger.warning("问题拆解调用失败，退化为单一问题：%s", e)
        return [question]

    return _parse_sub_queries(turn.content, question)


def _parse_sub_queries(raw: str, fallback: str) -> List[str]:
    """从模型输出里抠出 JSON 数组；格式不对、为空都退化为单一问题。"""
    if not raw or not raw.strip():
        return [fallback]

    match = _JSON_ARRAY_RE.search(raw)
    candidate = match.group(0) if match else raw.strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return [fallback]

    if not isinstance(parsed, list) or not parsed:
        return [fallback]

    queries = [str(q).strip() for q in parsed if str(q).strip()]
    if not queries:
        return [fallback]

    # 去重保序：模型偶尔会把同一个子问题写两遍
    seen = set()
    unique: List[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique[:MAX_SUB_QUERIES]
