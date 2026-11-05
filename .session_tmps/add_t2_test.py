import io

p = "backend/tests/test_trust.py"
t = io.open(p, encoding="utf-8").read()

anchor = '''def test_b4_ask_rate_limited(tmp_path, monkeypatch):'''

new_test = '''def test_rate_limit_ignores_spoofed_left_xff(tmp_path, monkeypatch):
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


'''

assert anchor in t, "anchor not found"
t = t.replace(anchor, new_test + anchor, 1)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("test added, total lines =", len(t.splitlines()))