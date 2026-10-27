"""事件 → SSE 文本：格式化、心跳、断连检测。"""
import asyncio
import json
from typing import AsyncIterator, Iterator

from starlette.concurrency import iterate_in_threadpool

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


async def stream_events(
    events: Iterator[dict], is_disconnected=None, heartbeat_seconds: float = HEARTBEAT_SECONDS
) -> AsyncIterator[str]:
    """把同步生成器包成异步生成器，空闲时发心跳，客户端断开后立刻停止。

    is_disconnected 是一个 async 可调用对象（通常是 request.is_disconnected）。
    """
    iterator = iterate_in_threadpool(events)
    pending: "asyncio.Task | None" = None
    try:
        while True:
            if is_disconnected is not None and await is_disconnected():
                break

            if pending is None:
                pending = asyncio.ensure_future(iterator.__anext__())

            done, _ = await asyncio.wait({pending}, timeout=heartbeat_seconds)
            if not done:
                # 长时间没有事件时发一行注释，防止代理把连接掐掉
                yield HEARTBEAT_LINE
                continue

            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            finally:
                pending = None

            yield format_event(event)
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
