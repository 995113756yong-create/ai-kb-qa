"""验证并发测试确实能抓到原 bug：临时移除锁内检查，测试应失败。"""
import io
import subprocess
import sys

p = "backend/app/agent_store.py"
orig = io.open(p, encoding="utf-8").read()

broken = orig.replace(
    """        with self._lock:
            # 锁内再查一次：上面那次检查在锁外，两个请求同时用同一个 ID 创建时
            # 都能通过，后写入的会覆盖前一个。
            if agent_id in self._agents:
                raise ValueError(f"agent_id 已存在：{agent_id}")
            self._agents[agent_id] = entry""",
    """        with self._lock:
            self._agents[agent_id] = entry""",
)
assert broken != orig, "could not revert patch"

io.open(p, "w", encoding="utf-8", newline="").write(broken)
try:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_agent_store_concurrency.py", "-q"],
        cwd="backend",
        capture_output=True,
        text=True,
    )
    tail = r.stdout.strip().splitlines()[-3:]
    print("WITHOUT fix -> exit", r.returncode)
    for l in tail:
        print("  ", l)
finally:
    io.open(p, "w", encoding="utf-8", newline="").write(orig)
    print("restored original")
