import os

from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.qa import EMPTY_KB_ANSWER, PROMPT_TEMPLATE
from tests.conftest import FAKE_ANSWER


def _upload(client, name, content, ctype="text/plain"):
    return client.post("/api/upload", files={"file": (name, content, ctype)})


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_frontend_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "AI 知识库问答" in r.text


def test_frontend_path_traversal_blocked(client):
    """回归测试：原兜底路由可用 /..%2F..%2F.env 读到任意文件。"""
    for url in [
        "/..%2F..%2Fbackend%2Fapp%2Fconfig.py",
        "/%2E%2E/%2E%2E/backend/app/config.py",
        "/..%2F..%2F..%2F..%2Fetc%2Fpasswd",
    ]:
        r = client.get(url)
        assert r.status_code == 404, url
        assert "OPENAI_API_KEY" not in r.text
        assert "root:" not in r.text


def test_upload_and_list(client):
    r = _upload(client, "笔记.txt", "知识库里有一句话：答案是 42。".encode("utf-8"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == "笔记.txt" and body["chunks"] == 1

    docs = client.get("/api/docs").json()["docs"]
    assert len(docs) == 1 and docs[0]["filename"] == "笔记.txt"


def test_upload_filename_traversal_stays_in_upload_dir(client, dirs):
    """回归测试：原实现直接用 file.filename 拼路径。"""
    upload_dir, _ = dirs
    r = _upload(client, "../../evil.txt", b"hello")
    assert r.status_code == 200, r.text
    assert r.json()["filename"] == "evil.txt"

    parent = os.path.dirname(upload_dir)
    assert not os.path.exists(os.path.join(parent, "evil.txt"))
    assert not os.path.exists(os.path.join(os.path.dirname(parent), "evil.txt"))
    saved = os.listdir(upload_dir)
    assert saved == [r.json()["doc_id"] + ".txt"]


def test_upload_rejects_bad_extension(client, dirs):
    r = _upload(client, "run.sh", b"rm -rf /")
    assert r.status_code == 400
    assert os.listdir(dirs[0]) == []


def test_upload_rejects_too_large(client, dirs):
    r = _upload(client, "big.txt", b"a" * (1024 * 1024 + 1))
    assert r.status_code == 413
    assert os.listdir(dirs[0]) == []


def test_upload_rejects_empty(client):
    assert _upload(client, "empty.txt", b"").status_code == 400


def test_ask_empty_kb(client):
    r = client.post("/api/ask", json={"question": "答案是多少？"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "question": "答案是多少？", "answer": EMPTY_KB_ANSWER, "sources": []}


def test_ask_returns_answer_with_sources(client):
    _upload(client, "笔记.txt", "答案是 42。".encode("utf-8"))
    r = client.post("/api/ask", json={"question": "答案是 42。"})
    body = r.json()
    assert r.status_code == 200
    assert body["answer"] == FAKE_ANSWER
    src = body["sources"][0]
    assert src["index"] == 1 and src["source"] == "笔记.txt" and "42" in src["snippet"]


def test_ask_validation(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={"question": "   "}).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 1001}).status_code == 422


def test_prompt_is_readable_chinese():
    assert "知识库问答助手" in PROMPT_TEMPLATE
    assert "{context}" in PROMPT_TEMPLATE and "{question}" in PROMPT_TEMPLATE


def test_missing_api_key_still_starts(monkeypatch, dirs):
    """没配 Key 时服务照常启动，上传/问答返回 503 而不是整个进程起不来。"""
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)
    app = create_app(upload_dir=dirs[0], index_dir=dirs[1])
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/docs").json()["docs"] == []
        assert c.post("/api/ask", json={"question": "hi"}).status_code == 503
        assert _upload(c, "a.txt", b"hello").status_code == 503
