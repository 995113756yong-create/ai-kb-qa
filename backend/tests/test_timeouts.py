"""Model and embedding client timeouts.

Constructing a client only -- no network access. CI has no OPENAI_API_KEY,
so every construction must pass an explicit key.
"""
from app import config
from app.agent.llm import OpenAICompatibleLLM


def test_openai_client_uses_configured_timeout_and_retries(monkeypatch):
    monkeypatch.setattr(config, "LLM_TIMEOUT_SECONDS", 12)
    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 0)

    llm = OpenAICompatibleLLM(api_key="test-key")

    assert llm._client.timeout == 12
    assert llm._client.max_retries == 0


def test_defaults_are_bounded():
    assert config.LLM_TIMEOUT_SECONDS > 0
    assert config.LLM_TIMEOUT_SECONDS <= 300
    assert config.LLM_MAX_RETRIES >= 0
    assert config.LLM_MAX_RETRIES <= 3
    assert config.EMBEDDING_TIMEOUT_SECONDS > 0
    assert config.EMBEDDING_TIMEOUT_SECONDS <= 300


def test_chat_and_embedding_clients_accept_timeout(monkeypatch):
    """ChatOpenAI / OpenAIEmbeddings accept timeout and max_retries.

    Set OPENAI_API_KEY explicitly: langchain builds its own client and CI has
    no real key, so relying on the environment would fail there.
    """
    monkeypatch.setattr(config, "LLM_TIMEOUT_SECONDS", 15)
    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(config, "EMBEDDING_TIMEOUT_SECONDS", 20)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "OPENAI_API_BASE", "https://example.invalid/v1")

    from app.document import get_embeddings
    from app.qa import get_llm

    chat = get_llm()
    embed = get_embeddings()

    assert chat.request_timeout == 15
    assert embed.request_timeout == 20
    assert chat.max_retries == 1
    assert embed.max_retries == 1
