import io

p = "backend/app/agent/sse.py"
t = io.open(p, encoding="utf-8").read()

old = """    iterator = iterate_in_threadpool(events)"""
new = """    iterator = iterate_in_threadpool(events)
    # iterate_in_threadpool 是异步生成器，本身没有 close；要关的是底层同步生成器，
    # 它被包在 __wrapped__ 里（starlette 的实现细节，取不到时退回 events 自身）。
    source = getattr(iterator, "__wrapped__", events)"""
assert old in t
t = t.replace(old, new, 1)

old_fin = """        closer = getattr(events, "close", None)"""
new_fin = """        closer = getattr(source, "close", None) or getattr(events, "close", None)"""
assert old_fin in t
t = t.replace(old_fin, new_fin, 1)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("sse.py: closer now resolves to the underlying sync generator")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")