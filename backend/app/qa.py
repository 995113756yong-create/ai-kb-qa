import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from app.config import OPENAI_API_KEY, OPENAI_API_BASE, CHAT_MODEL
from app.document import load_faiss


def get_vectorstore():
    return load_faiss()


def build_rag_chain():
    """Build RAG chain: retrieve -> prompt -> LLM -> answer"""
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    template = """You are a helpful assistant. Answer the question based on the context below.
If the answer is not in the context, say I cannot find the answer in the document.

Context:
{context}

Question: {question}

Answer:"""

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
    chain = build_rag_chain()
    answer = chain.invoke(question)
    return answer
