"""事件 → SSE 文本：格式化、心跳、断连检测。"""
import asyncio
import json
import logging
from typing import AsyncIterator, Iterator

import anyio
from starlette.concurrency import iterate_in_threadpool

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15
HEARTBEAT_LINE = ": ping\n\n"

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def format_event(event: dict) -> str:
    """每个事件是 event: <type>\\ndata: <json>\\n\\n，data 里仍保留 type 方便前端复用类型。"""
    event_type = event.get("type", "message")
    payload = json.dumps(event, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _next_event(iterator: Iterator[dict]) -> tuple:
    """在线程里取下一个事件，返回 (是否结束, 事件)。"""
    try:
        return False, next(iterator)
    except StopIteration:
        return True, None


def _safe_close(closer) -> None:
    """关闭事件生成器；失败只记日志，不影响已发出的响应。"""
    try:
        closer()
    except Exception:
        logger.warning("关闭事件生成器失败", exc_info=True)


async def stream_events(
    events: Iterator[dict], is_disconnected=None, heartbeat_seconds: float = HEARTBEAT_SECONDS
) -> AsyncIterator[str]:
    """把同步生成器包成异步生成器，空闲时发心跳，客户端断开后立刻停止。

    is_disconnected 是一个 async 可调用对象（通常是 request.is_disconnected）。

    结束时主动 close 底层生成器：run_agent 依赖 GeneratorExit 补写 stopped 运行日志，
    只靠 GC 回收时机不确定，会话停止后可能迟迟不落日志。
    """
    pending: "asyncio.Task | None" = None
    try:
        while True:
            if is_disconnected is not None and await is_disconnected():
                break

            if pending is None:
                # 直接用 run_sync 驱动同步生成器，才能持有它的引用去 close；
                # iterate_in_threadpool 是异步生成器，内部 iterator 拿不到。
                pending = asyncio.ensure_future(anyio.to_thread.run_sync(_next_event, events))

            done, _ = await asyncio.wait({pending}, timeout=heartbeat_seconds)
            if not done:
                # 长时间没有事件时发一行注释，防止代理把连接掐掉
                yield HEARTBEAT_LINE
                continue

            try:
                exhausted, event = pending.result()
            finally:
                pending = None

            if exhausted:
                break

            yield format_event(event)
    finally:
        closer = getattr(events, "close", None)
        if pending is not None and not pending.done():
            # 线程里的 next() 还没返回，cancel 也打断不了它。
            # 等它返回后再 close，否则会报 ValueError: generator already executing。
            pending.cancel()
            if closer is not None:
                pending.add_done_callback(lambda _f: _safe_close(closer))
        elif closer is not None:
            _safe_close(closer)
