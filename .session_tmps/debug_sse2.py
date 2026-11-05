import asyncio
import sys

sys.path.insert(0, "backend")

from app.agent.sse import stream_events

flag = {"closed": False, "entered": False}


def gen():
    flag["entered"] = True
    try:
        yield {"type": "answer_delta", "text": "a"}
        yield {"type": "answer_delta", "text": "b"}
    finally:
        flag["closed"] = True


calls = {"n": 0}


async def is_disconnected():
    calls["n"] += 1
    return calls["n"] > 1


async def drain():
    agen = stream_events(gen(), is_disconnected, heartbeat_seconds=0.01)
    got = []
    async for chunk in agen:
        got.append(chunk)
    # 显式 aclose，确保异步生成器的 finally 被执行
    await agen.aclose()
    return got


out = asyncio.run(drain())
print("yielded:", len(out))
print("entered:", flag["entered"])
print("closed:", flag["closed"])
print("calls:", calls["n"])
