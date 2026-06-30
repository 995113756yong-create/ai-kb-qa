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

    template = """����һ��֪ʶ���ʴ����֡���������¼��������ĵ����ݣ�������׼ȷ�ش��û������⡣

Ҫ��
1. ֻ�����ĵ����ݻش𣬲�Ҫ������Ϣ
2. �ش�Ҫ��ࡢ�ṹ��������ʹ���б�ͱ��
3. ����ĵ���û��������ݣ���ظ����ĵ���δ�ҵ������Ϣ��

�ĵ����ݣ�
{context}

�û����⣺{question}

�ش�"""

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
        return "֪ʶ��Ϊ�գ������ϴ��ĵ���"
    chain = build_rag_chain()
    answer = chain.invoke(question)
    return answer
