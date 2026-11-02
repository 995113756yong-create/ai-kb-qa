"""写接口鉴权与问答限流。

公网部署时写接口（建/删专家、上传、删文档）必须有口令保护，否则任何人
都能往知识库塞文档、删专家。问答接口加进程内滑动窗口限流，防止刷接口
打爆模型费用。

放在独立模块而不是 main.py：评测脚本和 MCP Server 都可能复用这两个能力。
"""
import threading
import time
from collections import deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

from app import config


def require_admin(request: Request) -> None:
    """FastAPI 依赖：ADMIN_TOKEN 为空时直接放行（本地开发）；否则比对请求头。"""
    token = config.ADMIN_TOKEN
    if not token:
        return
    import hmac

    supplied = request.headers.get("x-admin-token", "")
    if not hmac.compare_digest(supplied.encode(), token.encode()):
        raise HTTPException(status_code=401, detail="需要管理员口令")


def client_key(request: Request) -> str:
    """限流桶的 key：信任代理时取 XFF 第一个 IP，否则取直连地址。"""
    if config.TRUST_PROXY:
        xff = request.headers.get("x-forwarded-for", "")
        first = xff.split(",")[0].strip() if xff else ""
        if first:
            return first
    client = request.client
    return client.host if client else "unknown"


class RateLimiter:
    """进程内滑动窗口限流：dict[key, deque[timestamp]] 加锁。

    单进程部署（uvicorn 单 worker / 容器单实例）下够用；
    多副本部署需要换成 Redis，当前场景用不上。
    """

    def __init__(self, per_minute: int = 0, window_seconds: float = 60.0):
        self.per_minute = per_minute
        self.window = window_seconds
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = {}

    @property
    def enabled(self) -> bool:
        return self.per_minute > 0

    def check(self, key: str) -> None:
        """超限时抛 429；未超限记录本次请求。关闭状态（per_minute<=0）直接放行。"""
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.per_minute:
                raise HTTPException(
                    status_code=429,
                    detail="请求过于频繁，请稍后再试",
                )
            bucket.append(now)
