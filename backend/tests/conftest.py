import os
import sys

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import create_app  # noqa: E402


FAKE_ANSWER = "根据文档，答案是 42 [1]"


class FakeAgentLLM:
    """AgentLLM 协议的最小实现：run_agent 只用 chat 与 stream。

    用在 client fixture 里，让 /api/agent/stream 在没有 OPENAI_API_KEY 的
    CI 环境也能跑通（否则 agent_llm 为 None 会直接 503）。
    """

    def __init__(self, answer: str = FAKE_ANSWER):
        self.answer = answer
        self.calls = 0

    def chat(self, messages):  # noqa: ANN001
        from app.agent.llm import AssistantTurn

        self.calls += 1
        # 首轮返回一个检索工具调用，模拟真实 ReAct 的第一步
        if self.calls == 1:
            from app.agent.llm import ToolCall

            return AssistantTurn(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="search_kb",
                        arguments='{"query": "%s"}' % "检索",
                    )
                ],
            )
        return AssistantTurn(content="够了")

    def stream(self, messages):  # noqa: ANN001
        # 流式回答：逐字产出，供 run_agent 拼 answer_delta
        for i in range(0, len(self.answer), 8):
            yield self.answer[i : i + 8]


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
def fake_agent_llm():
    return FakeAgentLLM()


@pytest.fixture
def client(embeddings, llm, dirs, fake_agent_llm):
    upload_dir, index_dir = dirs
    app = create_app(
        embeddings=embeddings,
        llm=llm,
        upload_dir=upload_dir,
        index_dir=index_dir,
        max_upload_mb=1,
        agent_llm=fake_agent_llm,
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _default_feature_flags(monkeypatch):
    """全局默认关闭新特性，保证旧测试行为不变。

    - EVIDENCE_MIN_SIM = -1：证据门槛关闭（假 Embedding 的余弦不稳定）
    - ADMIN_TOKEN = ""：写接口不鉴权
    - RATE_LIMIT_PER_MIN = 0：问答不限流
    - INTENT_ROUTING_ENABLED = False：意图分流关闭
    需要测试这些特性的用例在自己的 fixture 里显式覆盖。
    """
    from app import config

    monkeypatch.setattr(config, "EVIDENCE_MIN_SIM", -1.0)
    monkeypatch.setattr(config, "ADMIN_TOKEN", "")
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 0)
    monkeypatch.setattr(config, "INTENT_ROUTING_ENABLED", False)
