import io

p = "backend/app/agent/sse.py"
t = io.open(p, encoding="utf-8").read()

# 1) 新增 logging
t = t.replace(
    '"""事件 → SSE 文本：格式化、心跳、断连检测。"""\nimport asyncio\nimport json\n',
    '"""事件 → SSE 文本：格式化、心跳、断连检测。"""\nimport asyncio\nimport json\nimport logging\n',
)
t = t.replace(
    "from starlette.concurrency import iterate_in_threadpool\n",
    'from starlette.concurrency import iterate_in_threadpool\n\nlogger = logging.getLogger(__name__)\n',
)

# 2) finally 块：主动 close 生成器，让 run_agent 能收到 GeneratorExit 补写 stopped 日志
old_finally = """    finally:
        if pending is not None and not pending.done():
            pending.cancel()"""

new_finally = """    finally:
        closer = getattr(events, "close", None)
        if pending is not None and not pending.done():
            # 线程里的 next() 还没返回，cancel 也打断不了它。
            # 等它返回后再 close，否则会报 ValueError: generator already executing。
            pending.cancel()
            if closer is not None:
                pending.add_done_callback(lambda _f: _safe_close(closer))
        elif closer is not None:
            _safe_close(closer)


def _safe_close(closer) -> None:
    \"\"\"关闭事件生成器；失败只记日志，不影响已发出的响应。\"\"\"
    try:
        closer()
    except Exception:
        logger.warning("关闭事件生成器失败", exc_info=True)"""

assert old_finally in t, "finally block not found"
t = t.replace(old_finally, new_finally, 1)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("sse.py updated")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")