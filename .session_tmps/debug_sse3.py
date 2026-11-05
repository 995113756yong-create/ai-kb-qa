import asyncio
import sys

sys.path.insert(0, "backend")

from app.agent.sse import stream_events

state = {"closed": False, "entered": False, "count": 0}


def gen():
    state["entered"] = True
    try:
        state["count"] += 1
        print("  [gen] before yield 1")
        yield {"type": "answer_delta", "text": "a"}
        state["count"] += 1
        print("  [gen] before yield 2")
        yield {"type": "answer_delta", "text": "b"}
    finally:
        print("  [gen] FINALLY")
        state["closed"] = True


calls = {"n": 0}


async def is_disconnected():
    calls["n"] += 1
    print(f"  [check] #{calls['n']}")
    return calls["n"] > 1


async def drain():
    agen = stream_events(gen(), is_disconnected, heartbeat_seconds=0.01)
    got = []
    async for chunk in agen:
        print("  [main] got chunk")
        got.append(chunk)
    print("  [main] loop ended")
    await agen.aclose()
    print("  [main] aclosed")
    return got


out = asyncio.run(drain())
print("RESULT yielded:", len(out), "entered:", state["entered"], "count:", state["count"], "closed:", state["closed"])
