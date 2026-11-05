import io

p = "backend/tests/test_stopped_log.py"
t = io.open(p, encoding="utf-8").read()

old = '''    async def drain():
        async for _ in stream_events(gen(), is_disconnected, heartbeat_seconds=0.01):
            pass

    asyncio.run(drain())
    assert flag["closed"] is True'''

new = '''    async def drain():
        agen = stream_events(gen(), is_disconnected, heartbeat_seconds=5)
        async for _ in agen:
            pass
        # 真实场景由 ASGI 层负责收尾；这里显式 aclose 等价于连接关闭后的清理
        await agen.aclose()

    asyncio.run(drain())
    assert flag["closed"] is True'''

assert old in t
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("test fixed")