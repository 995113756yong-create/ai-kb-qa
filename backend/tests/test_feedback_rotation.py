"""Feedback file rotation: /api/feedback needs no auth, each entry up to ~9.5KB,
so the file must have a size cap.

NOTE: create_app must receive the fake embeddings/llm, otherwise app.state.store
is None and every write endpoint returns 503. CI has no OPENAI_API_KEY, so this
must never rely on a real key.
"""
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app import config
from app.main import _append_feedback, create_app


def _client_with_log_dir(tmp_path, embeddings, llm, log_dir):
    app = create_app(
        embeddings=embeddings,
        llm=llm,
        upload_dir=str(tmp_path / "uploads"),
        index_dir=str(tmp_path / "faiss_index"),
        agent_log_dir=str(log_dir),
    )
    client = TestClient(app)
    client.__enter__()
    return client


def test_feedback_rotates_when_exceeding_limit(tmp_path, embeddings, llm, monkeypatch):
    monkeypatch.setattr(config, "FEEDBACK_MAX_MB", 0.0001)  # about 100 bytes
    log_dir = tmp_path / "logs"
    client = _client_with_log_dir(tmp_path, embeddings, llm, log_dir)

    payload = {
        "agent_id": "default",
        "question": "wen ti",
        "answer": "hui da",
        "rating": "down",
        "reason": "li you" * 10,
    }
    for _ in range(3):
        r = client.post("/api/feedback", json=payload)
        assert r.status_code == 200, r.text

    main_file = log_dir / "feedback.jsonl"
    rotated = log_dir / "feedback.jsonl.1"

    assert main_file.exists(), "expected %s to exist" % main_file
    assert rotated.exists(), "overtop limit should produce .1 archive"

    total = main_file.stat().st_size + rotated.stat().st_size
    assert total < 10 * 1024


def test_feedback_appends_without_rotation_under_limit(tmp_path, embeddings, llm, monkeypatch):
    monkeypatch.setattr(config, "FEEDBACK_MAX_MB", 100)  # 100MB
    log_dir = tmp_path / "logs2"
    client = _client_with_log_dir(tmp_path, embeddings, llm, log_dir)

    payload = {"agent_id": "default", "question": "q", "answer": "a", "rating": "up"}
    for _ in range(3):
        r = client.post("/api/feedback", json=payload)
        assert r.status_code == 200, r.text

    main_file = log_dir / "feedback.jsonl"
    assert main_file.exists()
    assert not (log_dir / "feedback.jsonl.1").exists()

    lines = [l for l in main_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3
    assert json.loads(lines[0])["rating"] == "up"


def test_append_feedback_helper_is_atomic_under_threads(tmp_path):
    path = str(tmp_path / "f.jsonl")

    def write(i: int) -> None:
        _append_feedback(path, json.dumps({"i": i}) + "\n", 0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(50)))

    lines = [l for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
    assert len(lines) == 50
    assert sorted(json.loads(l)["i"] for l in lines) == list(range(50))
