"""模型与 Embedding 客户端的超时/重试配置。

只构造客户端、不访问网络：验证 OpenAI SDK 确实收到了配置值。
"""
from app import config
from app.agent.llm import OpenAICompatibleLLM


def test_openai_client_uses_configured_timeout_and_retries(monkeypatch):
    """超时与重试次数来自配置，而不是 SDK 默认的 600 秒 / 2 次。"""
    monkeypatch.setattr(config, "LLM_TIMEOUT_SECONDS", 12)
    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 0)

    llm = OpenAICompatibleLLM(api_key="test-key")

    assert llm._client.timeout == 12
    assert llm._client.max_retries == 0


def test_defaults_are_bounded():
    """默认值必须有界：不能退化成 SDK 的 600 秒 / 2 次。"""
    assert config.LLM_TIMEOUT_SECONDS > 0
    assert config.LLM_TIMEOUT_SECONDS <= 300
    assert config.LLM_MAX_RETRIES >= 0
    assert config.LLM_MAX_RETRIES <= 3
    assert config.EMBEDDING_TIMEOUT_SECONDS > 0
    assert config.EMBEDDING_TIMEOUT_SECONDS <= 300


def test_chat_and_embedding_clients_accept_timeout(monkeypatch):
    """ChatOpenAI 与 OpenAIEmbeddings 也接受 timeout / max_retries 参数。"""
    monkeypatch.setattr(config, "LLM_TIMEOUT_SECONDS", 15)
    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(config, "EMBEDDING_TIMEOUT_SECONDS", 20)

    from app.document import get_embeddings
    from app.qa import get_llm

    chat = get_llm()
    embed = get_embeddings()

    # langchain 把 timeout 存在 request_timeout 上
    assert chat.request_timeout == 15
    assert embed.request_timeout == 20
    assert chat.max_retries == 1
    assert embed.max_retries == 1
