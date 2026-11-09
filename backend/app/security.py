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
from app.i18n import tr


def require_admin(request: Request) -> None:
    """FastAPI 依赖：ADMIN_TOKEN 为空时直接放行（本地开发）；否则比对请求头。"""
    token = config.ADMIN_TOKEN
    if not token:
        return
    import hmac

    supplied = request.headers.get("x-admin-token", "")
    if not hmac.compare_digest(supplied.encode(), token.encode()):
        raise HTTPException(status_code=401, detail=tr("auth.admin_required"))


def client_key(request: Request) -> str:
    """限流桶的 key。

    TRUST_PROXY=true 时取 XFF 最右侧的一项：它由离后端最近的可信代理
    （Next.js 转发层）写入。更靠左的值来自客户端，可以伪造——若取最左项，
    攻击者每次请求带一个随机 XFF 就能拿到新的限流桶，限流形同虚设。
    """
    if config.TRUST_PROXY:
        xff = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
    client = request.client
    return client.host if client else "unknown"


class RateLimiter:
    """进程内滑动窗口限流：dict[key, deque[timestamp]] 加锁。

    单进程部署（uvicorn 单 worker / 容器单实例）下够用；
    多副本部署需要换成 Redis，当前场景用不上。
    """

    def __init__(
        self,
        per_minute: int = 0,
        window_seconds: float = 60.0,
        max_keys: int = 10000,
    ):
        self.per_minute = per_minute
        self.window = window_seconds
        self.max_keys = max_keys
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = {}
        self._last_sweep = time.monotonic()

    @property
    def enabled(self) -> bool:
        return self.per_minute > 0

    def _sweep(self, now: float) -> None:
        """删除窗口内没有任何请求的 key。调用方需持有锁。"""
        stale = [k for k, b in self._hits.items() if not b or now - b[-1] > self.window]
        for k in stale:
            del self._hits[k]
        self._last_sweep = now

    def check(self, key: str) -> None:
        """超限时抛 429；未超限记录本次请求。关闭状态（per_minute<=0）直接放行。"""
        if not self.enabled:
            return
        now = time.monotonic()
        with self._lock:
            if now - self._last_sweep > self.window:
                self._sweep(now)
            if key not in self._hits and len(self._hits) >= self.max_keys:
                self._sweep(now)
                if len(self._hits) >= self.max_keys:
                    # 活跃 key 太多，大概率是攻击：拒绝新 key，宁可误拒也不放行
                    raise HTTPException(
                        status_code=429,
                        detail=tr("rate.limited"),
                    )
            bucket = self._hits.setdefault(key, deque())
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.per_minute:
                raise HTTPException(
                    status_code=429,
                    detail=tr("rate.limited"),
                )
            bucket.append(now)
