import io

src = '''"""反馈文件轮转: /api/feedback 不需要鉴权, 每条最大约 9.5KB, 必须设上限."""
import json
from concurrent.futures import ThreadPoolExecutor

from starlette.testclient import TestClient

from app import config
from app.main import _append_feedback, create_app


def _client_with_log_dir(tmp_path, log_dir):
    """用显式 log_dir 建 app.

    agent_log_dir 是 create_app 的默认参数, 只在函数定义时求值,
    monkeypatch 改 config.AGENT_LOG_DIR 影响不到它, 必须显式传.
    """
    app = create_app(agent_log_dir=str(log_dir))
    client = TestClient(app)
    client.__enter__()
    return client


def test_feedback_rotates_when_exceeding_limit(tmp_path, monkeypatch):
    """超过上限后主文件轮转为 .1, 不会无限增长."""
    monkeypatch.setattr(config, "FEEDBACK_MAX_MB", 0.0001)  # 约 100 字节
    log_dir = tmp_path / "logs"
    client = _client_with_log_dir(tmp_path, log_dir)

    payload = {
        "agent_id": "default",
        "question": "wen ti",
        "answer": "hui da",
        "rating": "down",
        "reason": "li you" * 10,
    }
    for _ in range(3):
        assert client.post("/api/feedback", json=payload).status_code == 200

    main_file = log_dir / "feedback.jsonl"
    rotated = log_dir / "feedback.jsonl.1"

    assert main_file.exists(), f"expected {main_file} to exist"
    assert rotated.exists(), "overtop limit should produce .1 archive"

    total = main_file.stat().st_size + rotated.stat().st_size
    assert total < 10 * 1024


def test_feedback_appends_without_rotation_under_limit(tmp_path, monkeypatch):
    """未超上限时正常追加, 不产生 .1."""
    monkeypatch.setattr(config, "FEEDBACK_MAX_MB", 100)  # 100MB
    log_dir = tmp_path / "logs2"
    client = _client_with_log_dir(tmp_path, log_dir)

    payload = {"agent_id": "default", "question": "q", "answer": "a", "rating": "up"}
    for _ in range(3):
        assert client.post("/api/feedback", json=payload).status_code == 200

    main_file = log_dir / "feedback.jsonl"
    assert main_file.exists()
    assert not (log_dir / "feedback.jsonl.1").exists()

    lines = [l for l in main_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3
    assert json.loads(lines[0])["rating"] == "up"


def test_append_feedback_helper_is_atomic_under_threads(tmp_path):
    """多线程同时写不会丢行."""
    path = str(tmp_path / "f.jsonl")

    def write(i: int) -> None:
        _append_feedback(path, json.dumps({"i": i}) + "\\n", 0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(50)))

    lines = [l for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]
    assert len(lines) == 50
    assert sorted(json.loads(l)["i"] for l in lines) == list(range(50))
'''

io.open("backend/tests/test_feedback_rotation.py", "w", encoding="utf-8", newline="").write(src)
print("written")

import py_compile
py_compile.compile("backend/tests/test_feedback_rotation.py", doraise=True)
print("compiles OK")