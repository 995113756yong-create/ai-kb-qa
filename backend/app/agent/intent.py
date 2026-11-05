"""规则意图识别：在进入 ReAct 循环前，用零成本的规则先把能确定的请求分流。

为什么需要：
ReAct 循环里"要不要检索、先查什么"完全交给模型决定，每个请求至少一次
带工具的 LLM 调用。但很多请求的意图一眼就能看出来：
- "你好""谢谢"这类寒暄根本不需要检索，走 ReAct 白白多一轮工具决策；
- "知识库里有哪些文档"直接列文档即可；
- 带配置号、型号编码的问题一定要查知识库，不该让模型去"判断要不要查"。

做法（两层）：
1. 规则层：只处理有把握的情况，按优先级依次匹配，命中即返回。
2. 大模型层：规则拿不准的（UNCERTAIN）原样交给 ReAct 循环，由模型自己决定。

规则宁可漏判也不误判：误判成闲聊会让本该检索的问题直接被回答，
所以闲聊必须是"整句都是寒暄"，夹带任何实际问题都不算。
"""
import re
from dataclasses import dataclass

CHAT = "chat"            # 寒暄 / 身份 / 致谢：不检索，直接回复
LIST_DOCS = "list_docs"  # 问知识库里有什么文档：直接列文档
KB_QUERY = "kb_query"    # 明确要查知识库：先用原问题检索一次，再进 ReAct
UNCERTAIN = "uncertain"  # 规则拿不准：交给 ReAct 循环里的模型判断

# 整句寒暄。匹配前先去掉标点和空白，必须整句命中才算闲聊。
_CHAT_PATTERNS = [
    r"(你好|您好|嗨|哈喽|hello|hi|hey)(呀|啊|吖)?",
    r"(早上好|上午好|中午好|下午好|晚上好|早安|晚安)",
    r"(谢谢|多谢|感谢|谢了|thanks|thankyou|thx)(你|您|啦|了)?",
    r"(好的|好|嗯|嗯嗯|ok|okay|收到|明白了|知道了|懂了)",
    r"(再见|拜拜|bye|byebye)",
    r"(你是谁|你叫什么|你叫什么名字|你是什么|你能做什么|你会什么|你有什么功能)(呀|啊|呢)?",
]
_CHAT_RE = re.compile(r"^(?:" + "|".join(_CHAT_PATTERNS) + r")+$", re.IGNORECASE)

# 问"知识库里有什么"
_LIST_DOCS_RE = re.compile(
    r"(知识库|资料库|文档库)(里|中)?(有|包含|都有)(哪些|什么|多少)(文档|文件|资料|内容)?"
    r"|(上传|导入)了(哪些|什么|多少)(文档|文件|资料)"
    r"|(有|有哪些|列出|列一下)(哪些)?(文档|文件)(吗)?$"
)

# 明确指向知识库的说法
_KB_HINT_RE = re.compile(r"(根据|按照|基于|参考)?(知识库|文档|资料|手册)(里|中|上|内)")

# 编号类实体：配置号、型号编码。这类专属信息模型不可能"凭常识"答对，必须检索。
_ID_RE = re.compile(r"(配置|编号|单号|工单)\s*[#:：]?\s*\d{3,}|\b[A-Z]{2,}\d{3,}\b")

_PUNCT_RE = re.compile(r"[\s，。！？、,.!?~～…:：;；\"'“”‘’()（）]+")


@dataclass
class IntentResult:
    intent: str
    reason: str      # 命中的规则，写进 SSE 事件和运行日志，方便排查误判
    skip_llm_decision: bool  # True 表示规则已经决定了怎么走，不再让模型判断要不要检索


def classify(question: str) -> IntentResult:
    text = (question or "").strip()
    compact = _PUNCT_RE.sub("", text).lower()

    if not compact:
        return IntentResult(UNCERTAIN, "空问题", False)

    # 1. 闲聊：整句都是寒暄才算，最先判断，命中后整个检索流程都可以跳过
    if len(compact) <= 20 and _CHAT_RE.match(compact):
        return IntentResult(CHAT, "整句寒暄/致谢/身份询问", True)

    # 2. 问文档清单
    if _LIST_DOCS_RE.search(text):
        return IntentResult(LIST_DOCS, "询问知识库文档清单", True)

    # 3. 明确要查知识库：带编号实体，或者明说"文档里/知识库中"
    if _ID_RE.search(text):
        return IntentResult(KB_QUERY, "包含配置号/型号等编号实体", True)
    if _KB_HINT_RE.search(text):
        return IntentResult(KB_QUERY, "明确指向知识库/文档", True)

    # 4. 兜底：交给 ReAct 循环里的模型自己判断
    return IntentResult(UNCERTAIN, "规则未命中，交给模型判断", False)
