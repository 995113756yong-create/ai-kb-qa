"""问答：检索 Top-K 片段 → 拼装带编号的上下文 → 大模型生成回答，并返回出处。"""
from typing import List

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import CHAT_MODEL, OPENAI_API_BASE, OPENAI_API_KEY, TOP_K
from app.document import KnowledgeBase

EMPTY_KB_ANSWER = "知识库为空，请先上传文档。"
NOT_FOUND_ANSWER = "文档中未找到相关信息。"
SNIPPET_LEN = 200

PROMPT_TEMPLATE = """你是一个知识库问答助手。请严格根据下面提供的文档片段回答用户的问题。

要求：
1. 只能使用文档片段中的信息回答，不要编造或补充文档以外的内容。
2. 回答要简洁、有条理，必要时使用列表。
3. 在用到某个片段的句子末尾标注片段编号，例如 [1]、[2]。
4. 如果文档片段中没有与问题相关的内容，直接回答：“文档中未找到相关信息。”

文档片段：
{context}

用户问题：{question}

回答："""


def get_llm() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=CHAT_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
        temperature=0.1,
    )


def _location(doc: Document) -> str:
    page = doc.metadata.get("page")
    source = doc.metadata.get("source", "未知文档")
    return f"{source} 第{page}页" if page else source


def format_context(docs: List[Document]) -> str:
    return "\n\n".join(
        f"[{i}] 来源：{_location(d)}\n{d.page_content}" for i, d in enumerate(docs, start=1)
    )


def to_sources(docs: List[Document]) -> List[dict]:
    return [
        {
            "index": i,
            "doc_id": d.metadata.get("doc_id"),
            "source": d.metadata.get("source"),
            "page": d.metadata.get("page"),
            "snippet": d.page_content[:SNIPPET_LEN],
        }
        for i, d in enumerate(docs, start=1)
    ]


class QAService:
    """持有知识库和大模型，链只构建一次，之后每次提问复用。"""

    def __init__(self, kb: KnowledgeBase, llm: BaseChatModel, top_k: int = TOP_K):
        self.kb = kb
        self.top_k = top_k
        self.chain = ChatPromptTemplate.from_template(PROMPT_TEMPLATE) | llm | StrOutputParser()

    def ask(self, question: str) -> dict:
        if self.kb.is_empty:
            return {"answer": EMPTY_KB_ANSWER, "sources": []}

        docs = self.kb.search(question, k=self.top_k)
        if not docs:
            return {"answer": NOT_FOUND_ANSWER, "sources": []}

        answer = self.chain.invoke({"context": format_context(docs), "question": question})
        return {"answer": answer, "sources": to_sources(docs)}
