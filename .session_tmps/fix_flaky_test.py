import io

src = '''"""限流桶的生命周期管理: 过期清理与 key 数量上限.

这两条防的是同一个问题: _hits 只增不删, 配合"伪造 IP 可换桶",
内存会持续增长直到进程被 OOM 杀掉.

注意: 这里不依赖真实 sleep 判断时序 -- CI 机器负载高时 sleep 精度不可靠,
会随机失败. 改为把 time.monotonic 打桩成可控的假时钟.
"""
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.security import RateLimiter


class FakeClock:
    """可手动推进的单调时钟."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_expired_keys_are_swept():
    """窗口内没有请求的 key 会被清掉, 不会永久驻留."""
    clock = FakeClock()
    with patch("app.security.time.monotonic", clock):
        limiter = RateLimiter(per_minute=5, window_seconds=60)
        limiter.check("a")
        assert "a" in limiter._hits

        clock.advance(61)
        # 触发下一次 check 时距离上次 sweep 已超过窗口, 会先清理
        limiter.check("b")
        assert "a" not in limiter._hits
        assert "b" in limiter._hits


def test_key_limit_rejects_new_keys():
    """活跃 key 达到上限后, 新 key 被拒; 已有 key 仍可正常使用."""
    limiter = RateLimiter(per_minute=5, window_seconds=60, max_keys=2)
    limiter.check("a")
    limiter.check("b")

    with pytest.raises(HTTPException) as excinfo:
        limiter.check("c")
    assert excinfo.value.status_code == 429

    # 已有 key 不受影响
    limiter.check("a")
    limiter.check("b")


def test_disabled_limiter_never_touches_state():
    """per_minute<=0 时关闭限流, 也不应记录任何状态."""
    limiter = RateLimiter(per_minute=0)
    for _ in range(100):
        limiter.check("any")
    assert limiter._hits == {}


def test_window_slides():
    """同一 key 超过 per_minute 后拒绝, 窗口滑过后恢复."""
    clock = FakeClock()
    with patch("app.security.time.monotonic", clock):
        limiter = RateLimiter(per_minute=2, window_seconds=60)
        limiter.check("k")
        limiter.check("k")
        with pytest.raises(HTTPException):
            limiter.check("k")

        clock.advance(61)
        limiter.check("k")  # 窗口滑过, 旧记录被丢弃
'''

io.open("backend/tests/test_security.py", "w", encoding="utf-8", newline="").write(src)
print("test_security.py rewritten with fake clock")

import py_compile
py_compile.compile("backend/tests/test_security.py", doraise=True)
print("compiles OK")