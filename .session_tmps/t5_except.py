import io

p = "backend/app/agent/runner.py"
t = io.open(p, encoding="utf-8").read()

old = """        yield {"type": "error", "detail": f"大模型调用失败：{type(e).__name__}"}
        _write_run_log(log_dir, question, steps, registry, "", False, elapsed(), error=str(e))"""

new = """        # 先写日志再 yield：yield 之后前端可能立刻断开，生成器就不再往下走了
        _write_run_log(log_dir, question, steps, registry, "", False, elapsed(), error=str(e))
        yield {"type": "error", "detail": f"大模型调用失败：{type(e).__name__}"}"""

assert old in t, "except block not found"
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("except block reordered")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")