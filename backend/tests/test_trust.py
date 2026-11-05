"""B1-B4 修复验证 + 鉴权限流 + 回答模式 + 用量统计测试."""
import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app import config
from app.agent.llm import AssistantTurn, ToolCall, Usage
from app.agent.runner import run_agent
from app.agent_store import effective_mode
from app.main import create_app
from app.seed_agents import FITNESS_AGENT_ID


# ---------- 测试用假 LLM ----------


class ScriptedAgentLLM:
    """第一轮调 search_kb，第二轮收尾；stream 可带 Usage。"""

    def __init__(self, answer="回答完成 [E1]", answer_usage=None):
        self.answer = answer
        self.answer_usage = answer_usage
        self.calls = 0
        self.stream_messages = None
        self.chat_messages_list = []

    def chat(self, messages, tools=None):
        self.chat_messages_list.append(messages)
        self.calls += 1
        if self.calls == 1:
            return AssistantTurn(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="search_kb", arguments=json.dumps({"query": "苹果"}, ensure_ascii=False))
                ],
            )
        return AssistantTurn(content="信息足够")

    def stream(self, messages):
        self.stream_messages = messages
        yield self.answer
        if self.answer_usage is not None:
            yield self.answer_usage


def _client(tmp_path, embeddings, agent_llm, **kw):
    app = create_app(
        embeddings=embeddings,
        llm=FakeListChatModel(responses=["固定 RAG 回答 [1]"]),
        upload_dir=str(tmp_path / "uploads"),
        index_dir=str(tmp_path / "faiss_index"),
        agent_log_dir=str(tmp_path / "logs"),
        agents_dir=str(tmp_path / "agents_store"),
        agent_llm=agent_llm,
        **kw,
    )
    c = TestClient(app)
    c.__enter__()
    return c


def _upload(c, filename="苹果.txt", text="苹果是一种水果", agent_id=None):
    url = "/api/upload" + (f"?agent_id={agent_id}" if agent_id else "")
    return c.post(url, files={"file": (filename, text.encode(), "text/plain")})


def _final_of(resp):
    events = []
    for block in resp.text.split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue
        data = next((l[6:] for l in block.split("\n") if l.startswith("data: ")), None)
        if data:
            events.append(json.loads(data))
    return events[-1]


# ---------- B1: persona 注入回答阶段 ----------


def test_b1_persona_in_answer_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_AGENT_ANSWER_MODE", "reference")
    embeddings = DeterministicFakeEmbedding(size=32)
    llm = ScriptedAgentLLM()
    c = _client(tmp_path, embeddings, llm)
    c.post(
        "/api/agents",
        json={"name": "教练", "persona": "你是务实健身教练", "agent_id": "coach"},
    )
    _upload(c, agent_id="coach")
    resp = c.post("/api/agent/stream", json={"question": "苹果", "agent_id": "coach"})
    assert resp.status_code == 200
    # stream_messages 是回答阶段的消息：system 应包含 persona
    sys_text = llm.stream_messages[0]["content"]
    assert "你是务实健身教练" in sys_text
    assert "你的角色设定" in sys_text


def test_b1_persona_in_no_evidence_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_AGENT_ANSWER_MODE", "reference")
    embeddings = DeterministicFakeEmbedding(size=32)
    llm = ScriptedAgentLLM(answer="通用回答")
    c = _client(tmp_path, embeddings, llm)
    c.post(
        "/api/agents",
        json={"name": "教练B", "persona": "你是务实教练", "agent_id": "coachb"},
    )
    # 不上传文档 → 走无证据兜底分支
    resp = c.post("/api/agent/stream", json={"question": "任何问题", "agent_id": "coachb"})
    assert resp.status_code == 200
    sys_text = llm.stream_messages[0]["content"]
    assert "你是务实教练" in sys_text


# ---------- B2: 日志目录用 effective_agent_id ----------


def test_b2_log_dir_effective_agent(tmp_path):
    embeddings = DeterministicFakeEmbedding(size=32)
    llm = ScriptedAgentLLM()
    c = _client(tmp_path, embeddings, llm)
    c.post("/api/agents", json={"name": "专家X", "agent_id": "agentx"})
    _upload(c, agent_id="agentx")
    # agent_id 只放查询串（不进 body）
    resp = c.post("/api/agent/stream?agent_id=agentx", json={"question": "苹果"})
    assert resp.status_code == 200
    log = tmp_path / "agents_store" / "agentx" / "logs" / "agent_runs.jsonl"
    assert log.exists(), "日志应写入 agentx 的目录（effective_agent_id）"


# ---------- B3: 专家 model 字段生效 ----------


def test_b3_model_factory_called_and_cached(tmp_path):
    embeddings = DeterministicFakeEmbedding(size=32)
    created = []

    def factory(model: str):
        created.append(model)
        return ScriptedAgentLLM()

    llm = ScriptedAgentLLM()
    c = _client(tmp_path, embeddings, llm, agent_llm_factory=factory)
    resp = c.post("/api/agents", json={"name": "M专家", "model": "foo/bar", "agent_id": "mx"})
    assert resp.status_code == 200
    _upload(c, agent_id="mx")

    r1 = c.post("/api/agent/stream", json={"question": "苹果", "agent_id": "mx"})
    assert r1.status_code == 200
    assert created == ["foo/bar"], "factory 应以专家配置的模型名被调用一次"

    r2 = c.post("/api/agent/stream", json={"question": "再问一次", "agent_id": "mx"})
    assert r2.status_code == 200
    assert created == ["foo/bar"], "第二次问答应复用缓存实例"


def test_b3_invalid_model_name_422(tmp_path):
    embeddings = DeterministicFakeEmbedding(size=32)
    c = _client(tmp_path, embeddings, ScriptedAgentLLM())
    resp = c.post("/api/agents", json={"name": "坏模型", "model": "not valid!"})
    assert resp.status_code == 422
    assert "模型名不合法" in resp.json()["detail"]


def test_b3_default_llm_when_no_model(tmp_path):
    embeddings = DeterministicFakeEmbedding(size=32)
    base = ScriptedAgentLLM()
    c = _client(tmp_path, embeddings, base, agent_llm_factory=lambda m: ScriptedAgentLLM())
    c.post("/api/agents", json={"name": "无模型", "agent_id": "nom"})
    _upload(c)
    resp = c.post("/api/agent/stream", json={"question": "苹果"})
    assert resp.status_code == 200


# ---------- B4: 鉴权与限流 ----------


def test_b4_admin_token_write_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_TOKEN", "abc")
    monkeypatch.setattr(config, "DEFAULT_AGENT_ANSWER_MODE", "reference")
    embeddings = DeterministicFakeEmbedding(size=32)
    c = _client(tmp_path, embeddings, ScriptedAgentLLM())

    headers_ok = {"X-Admin-Token": "abc"}

    # 不带 → 401
    assert c.post("/api/agents", json={"name": "x"}).status_code == 401
    # 错误头 → 401
    assert c.post("/api/agents", json={"name": "x", "agent_id": "xyz"}, headers={"X-Admin-Token": "bad"}).status_code == 401
    # 正确 → 成功（显式指定 agent_id，删除时才有确定目标）
    assert c.post("/api/agents", json={"name": "x", "agent_id": "xyz"}, headers=headers_ok).status_code == 200

    # 删专家 / 删文档 / 上传同理
    assert c.delete("/api/agents/xyz").status_code == 401
    assert c.delete("/api/agents/xyz", headers=headers_ok).status_code == 200
    assert c.post(
        "/api/upload", files={"file": ("a.txt", b"x", "text/plain")}
    ).status_code == 401
    assert c.post("/api/upload", files={"file": ("a.txt", "内容".encode("utf-8"), "text/plain")}, headers=headers_ok).status_code == 200
    doc_id = c.get("/api/docs").json()["docs"][0]["doc_id"]
    assert c.delete(f"/api/docs/{doc_id}").status_code == 401
    assert c.delete(f"/api/docs/{doc_id}", headers=headers_ok).status_code == 200

    # 问答不受鉴权影响
    assert c.get("/api/docs").status_code == 200
    assert c.get("/api/agents").status_code == 200


def test_b4_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 2)
    embeddings = DeterministicFakeEmbedding(size=32)
    c = _client(tmp_path, embeddings, ScriptedAgentLLM())
    _upload(c)

    codes = [
        c.post("/api/agent/stream", json={"question": "一"}).status_code,
        c.post("/api/agent/stream", json={"question": "二"}).status_code,
        c.post("/api/agent/stream", json={"question": "三"}).status_code,
    ]
    assert codes[:2] == [200, 200]
    assert codes[2] == 429


def test_b4_rate_limit_trust_proxy(tmp_path, monkeypatch):
    """TRUST_PROXY=true 时不同 XFF 地址各自计数。"""
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 1)
    monkeypatch.setattr(config, "TRUST_PROXY", True)
    embeddings = DeterministicFakeEmbedding(size=32)
    c = _client(tmp_path, embeddings, ScriptedAgentLLM())
    _upload(c)

    h1 = {"X-Forwarded-For": "1.1.1.1"}
    h2 = {"X-Forwarded-For": "2.2.2.2"}
    assert c.post("/api/agent/stream", json={"question": "a"}, headers=h1).status_code == 200
    assert c.post("/api/agent/stream", json={"question": "b"}, headers=h1).status_code == 429
    # 不同 IP 独立计数
    assert c.post("/api/agent/stream", json={"question": "c"}, headers=h2).status_code == 200


def test_rate_limit_ignores_spoofed_left_xff(tmp_path, monkeypatch):
    """伪造 XFF 左侧的 IP 无效：限流只认同一个可信代理写入的右侧项。

    真实链路里 Next.js 会把客户端 IP 覆盖到最右侧，左侧由客户端随意填写。
    若限流取最左项，攻击者每次换一个伪造 IP 就能拿到新的限流桶。
    """
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 1)
    monkeypatch.setattr(config, "TRUST_PROXY", True)
    embeddings = DeterministicFakeEmbedding(size=32)
    c = _client(tmp_path, embeddings, ScriptedAgentLLM())
    _upload(c)

    # 左侧 IP 不同，但右侧（可信代理写入）相同 -> 应共用同一个桶
    first = {"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}
    second = {"X-Forwarded-For": "8.8.8.8, 1.1.1.1"}
    assert c.post("/api/agent/stream", json={"question": "a"}, headers=first).status_code == 200
    assert c.post("/api/agent/stream", json={"question": "b"}, headers=second).status_code == 429


def test_b4_ask_rate_limited(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MIN", 1)
    embeddings = DeterministicFakeEmbedding(size=32)
    c = _client(tmp_path, embeddings, ScriptedAgentLLM())
    _upload(c)
    assert c.post("/api/ask", json={"question": "一"}).status_code == 200
    assert c.post("/api/ask", json={"question": "二"}).status_code == 429


# ---------- 回答模式 ----------


def test_mode_strict_no_evidence_fixed_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_AGENT_ANSWER_MODE", "strict")
    embeddings = DeterministicFakeEmbedding(size=32)
    llm = ScriptedAgentLLM()
    c = _client(tmp_path, embeddings, llm)
    # default 专家 + strict：空库直接固定话术
    resp = c.post("/api/agent/stream", json={"question": "任何问题"})
    final = _final_of(resp)
    assert final["answer"] == "文档中未找到相关信息。"
    assert final["mode"] == "strict"
    assert final["grounded"] is True
    assert final["grounded_ratio"] is None
    assert final["segments"] == []


def test_mode_request_override(tmp_path, monkeypatch):
    """请求体 answer_mode 覆盖专家配置（评测用通道）。"""
    monkeypatch.setattr(config, "DEFAULT_AGENT_ANSWER_MODE", "reference")
    embeddings = DeterministicFakeEmbedding(size=32)
    llm = ScriptedAgentLLM()
    c = _client(tmp_path, embeddings, llm)
    resp = c.post("/api/agent/stream", json={"question": "空库问题", "answer_mode": "strict"})
    final = _final_of(resp)
    assert final["mode"] == "strict"
    assert final["answer"] == "文档中未找到相关信息。"


def test_mode_reference_final_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_AGENT_ANSWER_MODE", "reference")
    embeddings = DeterministicFakeEmbedding(size=32)
    llm = ScriptedAgentLLM(answer="每周训练 3 次。[E1] 这句是一般知识补充。")
    c = _client(tmp_path, embeddings, llm)
    _upload(c)
    resp = c.post("/api/agent/stream", json={"question": "苹果"})
    final = _final_of(resp)
    assert final["mode"] == "reference"
    assert final["grounded_ratio"] is not None
    assert 0 <= final["grounded_ratio"] <= 1
    assert final["segments"], "final 应带句子级溯源"
    kinds = {s["kind"] for s in final["segments"]}
    assert "kb" in kinds
    # sources 每项有 content
    assert all("content" in s for s in final["sources"])
    # 无损拼接
    assert "".join(s["text"] for s in final["segments"]) == final["answer"]


def test_fitness_agent_is_reference_mode(tmp_path, monkeypatch):
    """健身专家播种为 reference 模式。"""
    embeddings = DeterministicFakeEmbedding(size=32)
    c = _client(tmp_path, embeddings, ScriptedAgentLLM())
    agents = {a["agent_id"]: a for a in c.get("/api/agents").json()["agents"]}
    assert agents[FITNESS_AGENT_ID]["answer_mode"] == "reference"
    assert agents["default"]["answer_mode"] == config.DEFAULT_AGENT_ANSWER_MODE


def test_agent_store_create_bad_answer_mode(tmp_path):
    from app.agent_store import AgentStore

    store = AgentStore(
        str(tmp_path / "s"), str(tmp_path / "u"), str(tmp_path / "i"), str(tmp_path / "l"),
        DeterministicFakeEmbedding(size=32),
    )
    with pytest.raises(ValueError):
        store.create(name="x", answer_mode="bad")
    entry = store.create(name="好", answer_mode="strict")
    assert entry["answer_mode"] == "strict"


def test_effective_mode_default_and_legacy(tmp_path):
    from app.agent_store import AgentStore

    assert effective_mode({"agent_id": "default"}) == config.DEFAULT_AGENT_ANSWER_MODE
    # 旧记录无 answer_mode 字段 → reference
    assert effective_mode({"agent_id": "x"}) == "reference"
    assert effective_mode({"agent_id": "x", "answer_mode": "strict"}) == "strict"


# ---------- 用量统计 ----------


def test_usage_accumulated_in_final(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_AGENT_ANSWER_MODE", "reference")
    embeddings = DeterministicFakeEmbedding(size=32)
    llm = ScriptedAgentLLM(answer_usage=Usage(prompt_tokens=100, completion_tokens=50))
    c = _client(tmp_path, embeddings, llm)
    _upload(c)
    resp = c.post("/api/agent/stream", json={"question": "苹果"})
    final = _final_of(resp)
    assert "usage" in final
    assert final["usage"]["llm_calls"] >= 2  # 研究循环 + 回答
    assert final["usage"]["prompt_tokens"] >= 100
    assert final["usage"]["completion_tokens"] >= 50


def test_usage_without_usage_still_works(tmp_path, monkeypatch):
    """旧假 LLM（stream 只 yield 字符串）不受 Usage 影响。"""
    monkeypatch.setattr(config, "DEFAULT_AGENT_ANSWER_MODE", "reference")
    embeddings = DeterministicFakeEmbedding(size=32)
    llm = ScriptedAgentLLM()  # answer_usage=None
    c = _client(tmp_path, embeddings, llm)
    _upload(c)
    resp = c.post("/api/agent/stream", json={"question": "苹果"})
    assert resp.status_code == 200
    final = _final_of(resp)
    assert final["usage"]["prompt_tokens"] == 0
