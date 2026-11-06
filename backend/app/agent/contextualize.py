"""多轮追问改写：把依赖上下文的追问改写成可以独立检索的完整问题。

只负责“理解问题”，不参与研究和回答：历史对话不进入 ReAct 循环和回答 prompt，
回答只能引用本轮登记的证据，防幻觉边界与单轮完全一致。
"""
import re
from typing import List, Optional

from app.agent.llm import AgentLLM

MAX_REWRITE_LEN = 300
HISTORY_ANSWER_CHARS = 600

# 追问特征：指代词、省略主语的承接词、对上一轮回答的操作
FOLLOWUP_RE = re.compile(
    r"(它|它们|这个|那个|这些|那些|这款|那款|该|其|上面|上述|前面|刚才|之前"
    r"|第[一二三四五六七八九十\d]+(点|条|个|项)"
    r"|呢[？?]?$|还有|另外|再|继续|展开|详细|具体|为什么|怎么算|对比一下|比较一下|换成|如果是)"
)

REWRITE_PROMPT = """你的任务是把用户的最新问题改写成一个“不看对话历史也能理解”的完整问题，用于知识库检索。

规则：
1. 补全指代和省略：把“它/这个/第二点/那 B 呢”等替换成对话中明确提到的具体对象。
2. 保留用户的意图和格式要求（如“用表格”“简短回答”），不要添加新的条件，不要回答问题。
3. 如果最新问题本身已经完整，原样输出。
4. 只输出改写后的问题，不要任何解释、引号或前缀。"""


def looks_like_followup(question: str, history: List[dict]) -> bool:
    """规则预判：没有历史的一律不改写；有历史时，短问题或带追问特征的才改写。"""
    if not history:
        return False
    q = question.strip()
    return len(q) <= 12 or bool(FOLLOWUP_RE.search(q))


def _strip_citations(text: str) -> str:
    return re.sub(r"\[\d+\]|【\d+】|\[E\d+\]", "", text)


def build_rewrite_messages(question: str, history: List[dict], max_turns: int) -> List[dict]:
    recent = history[-max_turns * 2:]
    lines = []
    for turn in recent:
        content = _strip_citations(turn.get("content", "")).strip()
        if turn.get("role") == "assistant":
            content = content[:HISTORY_ANSWER_CHARS]
            lines.append(f"助手：{content}")
        else:
            lines.append(f"用户：{content}")
    convo = "\n".join(lines)
    return [
        {"role": "system", "content": REWRITE_PROMPT},
        {"role": "user", "content": f"对话历史：\n{convo}\n\n最新问题：{question}\n\n改写后的问题："},
    ]


def contextualize(
    llm: AgentLLM, question: str, history: List[dict], max_turns: int
) -> Optional[str]:
    """返回改写后的问题；不需要改写、改写失败或结果异常时返回 None（调用方沿用原问题）。"""
    if not looks_like_followup(question, history):
        return None
    try:
        turn = llm.chat(build_rewrite_messages(question, history, max_turns))
    except Exception:
        return None
    text = (turn.content or "").strip().strip("\"'“”「」")
    text = re.sub(r"^(改写后的问题|问题)[：:]\s*", "", text)
    if not text or len(text) > MAX_REWRITE_LEN or text == question.strip():
        return None
    return text
