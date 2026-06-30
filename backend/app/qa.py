import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from app.config import OPENAI_API_KEY, OPENAI_API_BASE, CHAT_MODEL
from app.document import load_faiss, FAISS_DIR


def get_vectorstore():
    return load_faiss()


def build_rag_chain():
    """Build RAG chain: retrieve -> prompt -> LLM -> answer"""
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    template = """你是一个知识库问答助手。请根据以下检索到的文档内容，用中文准确回答用户的问题。

要求：
1. 只根据文档内容回答，不要编造信息
2. 回答要简洁、结构化，合理使用列表和表格
3. 如果文档中没有相关内容，请回复“文档中未找到相关信息”

文档内容：
{context}

用户问题：{question}

回答：""""

    prompt = ChatPromptTemplate.from_template(template)

    llm = ChatOpenAI(
        model=CHAT_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
    )

    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain


def ask(question: str) -> str:
    """Ask a question and get answer"""
    if not os.path.exists(os.path.join(FAISS_DIR, "index.faiss")):
        return "知识库为空，请先上传文档。"
    chain = build_rag_chain()
    answer = chain.invoke(question)
    return answer
