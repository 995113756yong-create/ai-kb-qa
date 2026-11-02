"""多专家平台测试：AgentStore CRUD + 专家级接口路由 + 种子播种 + 兼容性。

全部用假 Embedding / 假 LLM，不访问外网。
"""
import json
import os

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.agent_store import DEFAULT_AGENT_ID, AgentStore
from app.main import create_app
from app.seed_agents import FITNESS_AGENT_ID, ensure_seed_agents


@pytest.fixture
def embeddings():
    return DeterministicFakeEmbedding(size=32)


def _make_client(tmp_path, embeddings, agent_llm=None, seed=True):
    """多专家专用 TestClient：独立 agents_dir，可选不播种。"""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    app = create_app(
        embeddings=embeddings,
        llm=FakeListChatModel(responses=["固定 RAG 的假回答 [1]"]),
        upload_dir=str(tmp_path / "uploads"),
        index_dir=str(tmp_path / "faiss_index"),
        agent_log_dir=None,
        agents_dir=str(tmp_path / "agents_store"),
        agent_llm=agent_llm,
        seed_builtin=seed,
    )
    client = TestClient(app)
    client.__enter__()
    return client


# ---------- AgentStore 单元 ----------


def _store(tmp_path, embeddings) -> AgentStore:
    return AgentStore(
        str(tmp_path / "agents_store"),
        str(tmp_path / "uploads"),
        str(tmp_path / "faiss_index"),
        str(tmp_path / "logs"),
        embeddings,
    )


def test_store_default_agent_always_exists(tmp_path, embeddings):
    """default 专家永远存在，即使清单为空。"""
    store = _store(tmp_path, embeddings)
    entry = store.get("default")
    assert entry is not None
    assert entry["agent_id"] == "default"
    assert entry["builtin"] is True


def test_store_create_and_get(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    entry = store.create(name="健身教练", description="练", persona="你是教练", emoji="💪", agent_id="fitness")
    assert entry["agent_id"] == "fitness"
    assert entry["name"] == "健身教练"
    assert entry["builtin"] is False
    assert entry["created_at"]

    got = store.get("fitness")
    assert got["persona"] == "你是教练"


def test_store_create_generates_id(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    entry = store.create(name="随便")
    assert entry["agent_id"]
    assert entry["agent_id"] != "default"


def test_store_create_rejects_bad_id(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    with pytest.raises(ValueError):
        store.create(name="x", agent_id="default")
    with pytest.raises(ValueError):
        store.create(name="x", agent_id="非法ID!")
    with pytest.raises(ValueError):
        store.create(name="x", agent_id="fitness")
        store.create(name="y", agent_id="fitness")  # 重复


def test_store_create_rejects_empty_name(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    with pytest.raises(ValueError):
        store.create(name="  ")


def test_store_persists_across_restart(tmp_path, embeddings):
    """清单落盘：重启（新建 store）后专家还在。"""
    store = _store(tmp_path, embeddings)
    store.create(name="烹饪助手", agent_id="cooking")

    store2 = AgentStore(
        str(tmp_path / "agents_store"),
        str(tmp_path / "uploads"),
        str(tmp_path / "faiss_index"),
        str(tmp_path / "logs"),
        DeterministicFakeEmbedding(size=32),
    )
    assert store2.get("cooking") is not None


def test_store_delete_removes_data(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    store.create(name="临时", agent_id="tmp")
    agent_dir = store._agent_dir("tmp")
    assert os.path.isdir(agent_dir)

    removed = store.delete("tmp")
    assert removed["agent_id"] == "tmp"
    assert store.get("tmp") is None
    assert not os.path.exists(agent_dir)


def test_store_delete_default_returns_none(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    assert store.delete("default") is None


def test_store_delete_missing_returns_none(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    assert store.delete("no-such") is None


def test_store_list_default_first(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    store.create(name="B专家", agent_id="bbb")
    store.create(name="A专家", agent_id="aaa")
    agents = store.list_agents()
    assert agents[0]["agent_id"] == "default"
    assert {a["agent_id"] for a in agents[1:]} == {"aaa", "bbb"}


def test_store_kb_isolated_per_agent(tmp_path, embeddings):
    """关键：每个专家的知识库完全隔离——A 上传的文档 B 检索不到。"""
    store = _store(tmp_path, embeddings)
    store.create(name="A", agent_id="aaa")
    store.create(name="B", agent_id="bbb")

    from app.document import load_and_split

    upload_dir = store.upload_dir_of("aaa")
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, "secret.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("AAAAAAAAAAAAAAAA 机密内容")
    chunks = load_and_split(path, "d1", "secret.txt")
    store.kb("aaa").add_document("d1", "secret.txt", 100, chunks)

    docs_a = store.kb("aaa").list_documents()
    docs_b = store.kb("bbb").list_documents()
    assert len(docs_a) == 1 and docs_a[0]["filename"] == "secret.txt"
    assert docs_b == []

    hits_b = store.kb("bbb").search("机密内容", k=3)
    assert hits_b == []


def test_store_default_uses_legacy_dirs(tmp_path, embeddings):
    """default 专家沿用旧目录：已有部署的数据零迁移。"""
    store = _store(tmp_path, embeddings)
    assert store.upload_dir_of("default") == str(tmp_path / "uploads")
    assert store.index_dir_of("default") == str(tmp_path / "faiss_index")
    assert store.log_dir_of("default") == str(tmp_path / "logs")


# ---------- 种子播种 ----------


def test_seed_creates_fitness_agent(tmp_path, embeddings):
    store = _store(tmp_path, embeddings)
    created = ensure_seed_agents(store)
    assert FITNESS_AGENT_ID in created
    entry = store.get(FITNESS_AGENT_ID)
    assert entry["name"] == "健身教练"
    assert "健身" in entry["persona"]


def test_seed_is_idempotent(tmp_path, embeddings):
    """幂等：重复调用不再新建。"""
    store = _store(tmp_path, embeddings)
    ensure_seed_agents(store)
    created_again = ensure_seed_agents(store)
    assert FITNESS_AGENT_ID not in created_again


def test_seed_corpus_loaded_once(tmp_path, embeddings):
    """语料只在知识库为空时装载；用户删掉后不会自动塞回。"""
    store = _store(tmp_path, embeddings)
    ensure_seed_agents(store)
    docs = store.kb(FITNESS_AGENT_ID).list_documents()
    assert len(docs) >= 3  # 至少 4 份语料（可能因切分配置不同略有差异）

    # 删光后重新播种：不应再装
    for d in list(docs):
        store.kb(FITNESS_AGENT_ID).delete_document(d["doc_id"])
    assert store.kb(FITNESS_AGENT_ID).is_empty

    ensure_seed_agents(store)
    assert store.kb(FITNESS_AGENT_ID).is_empty, "用户删除后不应自动重装语料"


# ---------- HTTP 接口 ----------


def test_api_list_agents_includes_default_and_fitness(tmp_path, embeddings):
    client = _make_client(tmp_path, embeddings)
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()["agents"]
    ids = [a["agent_id"] for a in agents]
    assert ids[0] == "default"
    assert FITNESS_AGENT_ID in ids


def test_api_create_and_delete_agent(tmp_path, embeddings):
    client = _make_client(tmp_path, embeddings)
    resp = client.post(
        "/api/agents",
        json={"name": "烹饪助手", "description": "做菜", "persona": "你是厨师", "emoji": "🍳", "agent_id": "cooking"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agent_id"] == "cooking"

    listed = {a["agent_id"] for a in client.get("/api/agents").json()["agents"]}
    assert "cooking" in listed

    resp = client.delete("/api/agents/cooking")
    assert resp.status_code == 200
    listed = {a["agent_id"] for a in client.get("/api/agents").json()["agents"]}
    assert "cooking" not in listed


def test_api_create_agent_validation(tmp_path, embeddings):
    client = _make_client(tmp_path, embeddings)
    assert client.post("/api/agents", json={"name": ""}).status_code == 422
    assert client.post("/api/agents", json={"name": "x", "agent_id": "default"}).status_code == 422
    assert client.post("/api/agents", json={"name": "x", "agent_id": "bad id!"}).status_code == 422


def test_api_cannot_delete_default(tmp_path, embeddings):
    client = _make_client(tmp_path, embeddings)
    assert client.delete("/api/agents/default").status_code == 404


def test_api_docs_routed_per_agent(tmp_path, embeddings):
    """上传带 agent_id，文档只进该专家的知识库。"""
    client = _make_client(tmp_path, embeddings)
    client.post("/api/agents", json={"name": "B专家", "agent_id": "bbb"})

    r = client.post(
        "/api/upload?agent_id=bbb",
        files={"file": ("机密.txt", "BBB 机密内容".encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200, r.text

    docs_b = client.get("/api/docs?agent_id=bbb").json()["docs"]
    docs_default = client.get("/api/docs").json()["docs"]
    assert len(docs_b) == 1 and docs_b[0]["filename"] == "机密.txt"
    assert docs_default == []

    # 默认（不带参数）与显式 default 等价
    assert client.get("/api/docs?agent_id=default").json()["docs"] == docs_default


def test_api_upload_unknown_agent_404(tmp_path, embeddings):
    client = _make_client(tmp_path, embeddings)
    r = client.post(
        "/api/upload?agent_id=ghost",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 404


def test_api_delete_doc_per_agent(tmp_path, embeddings):
    client = _make_client(tmp_path, embeddings)
    client.post("/api/agents", json={"name": "B专家", "agent_id": "bbb"})
    doc_id = client.post(
        "/api/upload?agent_id=bbb",
        files={"file": ("x.txt", "内容".encode("utf-8"), "text/plain")},
    ).json()["doc_id"]

    # 从 default 视角删不到
    assert client.delete(f"/api/docs/{doc_id}").status_code == 404
    # 从正确的专家删
    assert client.delete(f"/api/docs/{doc_id}?agent_id=bbb").status_code == 200
    assert client.get("/api/docs?agent_id=bbb").json()["docs"] == []


# ---------- Agent 流按专家路由（SSE） ----------


class _ScriptedAgentLLM:
    """只实现 AgentLLM 协议：第一轮调 search_kb，第二轮收尾，然后流式回答。"""

    def __init__(self, answer="专家回答 [E1]"):
        self.answer = answer
        self.calls = 0

    def chat(self, messages, tools=None):
        from app.agent.llm import AssistantTurn, ToolCall

        self.calls += 1
        if self.calls == 1:
            return AssistantTurn(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="search_kb", arguments=json.dumps({"query": "机密"}, ensure_ascii=False))
                ],
            )
        return AssistantTurn(content="够了", tool_calls=[])

    def stream(self, messages):
        self.streamed = messages
        yield self.answer


def test_agent_stream_per_agent_routing(tmp_path, embeddings):
    """SSE 流按 agent_id 路由：bbb 的专家只能检索到 bbb 的文档，且 persona 注入了 prompt。"""
    client = _make_client(tmp_path, embeddings, agent_llm=_ScriptedAgentLLM())
    client.post("/api/agents", json={"name": "B专家", "persona": "你是B领域专家", "agent_id": "bbb"})
    client.post(
        "/api/upload?agent_id=bbb",
        files={"file": ("机密.txt", "BBB 机密文档内容".encode("utf-8"), "text/plain")},
    )

    resp = client.post("/api/agent/stream", json={"question": "机密是什么", "agent_id": "bbb"})
    assert resp.status_code == 200

    events = []
    for block in resp.text.split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue
        data = next((l[6:] for l in block.split("\n") if l.startswith("data: ")), None)
        if data:
            events.append(json.loads(data))

    final = events[-1]
    assert final["type"] == "final"
    # 只能引用 bbb 知识库里的文档
    assert final["sources"], "应检索到 bbb 的文档"
    assert all(s["source"] == "机密.txt" for s in final["sources"])


def test_agent_stream_default_backward_compat(tmp_path, embeddings):
    """不带 agent_id 的旧调用：行为与原来完全一致（default 知识库）。"""
    client = _make_client(tmp_path, embeddings, agent_llm=_ScriptedAgentLLM())
    client.post(
        "/api/upload",
        files={"file": ("默认文档.txt", "默认知识库内容".encode("utf-8"), "text/plain")},
    )
    resp = client.post("/api/agent/stream", json={"question": "内容"})
    assert resp.status_code == 200
    assert '"type": "final"' in resp.text or '"type":"final"' in resp.text


def test_agent_stream_unknown_agent_404(tmp_path, embeddings):
    client = _make_client(tmp_path, embeddings, agent_llm=_ScriptedAgentLLM())
    assert client.post("/api/agent/stream", json={"question": "hi", "agent_id": "ghost"}).status_code == 404


# ---------- 无 Key 环境 ----------


def test_no_key_agents_endpoints_503(tmp_path, monkeypatch):
    """无 Key 时服务照常启动：agents 接口 503，docs 仍返回空列表。"""
    from app import config as cfg

    monkeypatch.setattr(cfg, "OPENAI_API_KEY", None)
    app = create_app(
        upload_dir=str(tmp_path / "u"),
        index_dir=str(tmp_path / "i"),
        agents_dir=str(tmp_path / "agents"),
    )
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/docs").json()["docs"] == []
        assert c.get("/api/agents").status_code == 503
        assert c.post("/api/agents", json={"name": "x"}).status_code == 503
