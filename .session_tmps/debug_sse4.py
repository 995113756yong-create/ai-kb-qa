import asyncio
import sys

sys.path.insert(0, "backend")

from app.agent.sse import stream_events

state = {"closed": False, "count": 0}


def gen():
    try:
        state["count"] += 1
        yield {"type": "answer_delta", "text": "aaa"}
        state["count"] += 1
        yield {"type": "answer_delta", "text": "bbb"}
    finally:
        state["closed"] = True


calls = {"n": 0}


async def is_disconnected():
    calls["n"] += 1
    return calls["n"] > 1


async def drain():
    agen = stream_events(gen(), is_disconnected, heartbeat_seconds=5)
    got = []
    async for chunk in agen:
        got.append(chunk)
    await agen.aclose()
    return got


out = asyncio.run(drain())
print("chunks:")
for c in out:
    print("  ", repr(c[:80]))
print("gen count:", state["count"], "closed:", state["closed"])
