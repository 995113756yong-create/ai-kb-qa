import os
import sys

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import create_app  # noqa: E402

FAKE_ANSWER = "根据文档，答案是 42 [1]"


@pytest.fixture
def embeddings():
    # 同一段文本永远得到同一个向量，用原文检索时能稳定命中
    return DeterministicFakeEmbedding(size=32)


@pytest.fixture
def llm():
    return FakeListChatModel(responses=[FAKE_ANSWER])


@pytest.fixture
def dirs(tmp_path):
    upload_dir = tmp_path / "uploads"
    index_dir = tmp_path / "faiss_index"
    return str(upload_dir), str(index_dir)


@pytest.fixture
def client(embeddings, llm, dirs):
    upload_dir, index_dir = dirs
    app = create_app(
        embeddings=embeddings,
        llm=llm,
        upload_dir=upload_dir,
        index_dir=index_dir,
        max_upload_mb=1,
    )
    with TestClient(app) as c:
        yield c
