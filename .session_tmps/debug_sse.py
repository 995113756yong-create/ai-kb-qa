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
    yielded = []
    async for chunk in stream_events(gen(), is_disconnected, heartbeat_seconds=0.01):
        yielded.append(chunk)
    return yielded


out = asyncio.run(drain())
print("yielded:", len(out))
print("generator entered:", flag["entered"])
print("generator closed:", flag["closed"])
print("closer attr:", hasattr(gen(), "close"))
print("disconnected checks:", calls["n"])
