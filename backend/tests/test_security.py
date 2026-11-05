"""限流桶的生命周期管理：过期清理与 key 数量上限。

这两条防的是同一个问题：_hits 只增不删，配合「伪造 IP 可换桶」，
内存会持续增长直到进程被 OOM 杀掉。
"""
import time

import pytest
from fastapi import HTTPException

from app.security import RateLimiter


def test_expired_keys_are_swept():
    """窗口内没有请求的 key 会被清掉，不会永久驻留。"""
    limiter = RateLimiter(per_minute=5, window_seconds=0.05)
    limiter.check("a")
    assert "a" in limiter._hits

    time.sleep(0.06)
    # 触发下一次 check 时，距离上次 sweep 已超过窗口，会先清理
    limiter.check("b")
    assert "a" not in limiter._hits
    assert "b" in limiter._hits


def test_key_limit_rejects_new_keys():
    """活跃 key 达到上限后，新 key 被拒；已有 key 仍可正常使用。"""
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
    """per_minute<=0 时关闭限流，也不应记录任何状态。"""
    limiter = RateLimiter(per_minute=0)
    for _ in range(100):
        limiter.check("any")
    assert limiter._hits == {}


def test_window_slides():
    """同一 key 超过 per_minute 后拒绝，窗口滑过后恢复。"""
    limiter = RateLimiter(per_minute=2, window_seconds=0.05)
    limiter.check("k")
    limiter.check("k")
    with pytest.raises(HTTPException):
        limiter.check("k")

    time.sleep(0.06)
    limiter.check("k")  # 窗口滑过，旧记录被丢弃
