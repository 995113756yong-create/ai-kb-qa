import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from app.config import OPENAI_API_KEY, OPENAI_API_BASE, EMBEDDING_MODEL

FAISS_DIR = os.path.join(os.path.dirname(__file__), "..", "faiss_index")


def get_embeddings():
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
        check_embedding_ctx_length=False,
    )


def load_and_split(file_path: str):
    if file_path.endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    else:
        loader = TextLoader(file_path, encoding="utf-8")
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )
    chunks = splitter.split_documents(pages)
    return chunks


def store_to_faiss(chunks):
    embeddings = get_embeddings()
    vectorstore = FAISS.from_documents(
        documents=chunks,
        embedding=embeddings,
    )
    vectorstore.save_local(FAISS_DIR)
    return vectorstore


def load_faiss():
    embeddings = get_embeddings()
    return FAISS.load_local(
        FAISS_DIR,
        embeddings,
        allow_dangerous_deserialization=True,
    )
