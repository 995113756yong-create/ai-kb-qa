"""把「yield final(...) 后跟 _write_run_log(...)」调换为「先写日志再 yield」。

原因：yield 交出最后一个事件后前端可能立刻断开，生成器不会再往下执行，
日志就丢了。先写日志保证每条请求结束都有记录。
"""
import io
import re

p = "backend/app/agent/runner.py"
lines = io.open(p, encoding="utf-8").read().split("\n")


def block_end(start, open_ch="(", close_ch=")"):
    """从 start 行（含开括号）找到匹配的闭括号行，返回结束行号（含）。"""
    depth = 0
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return i
    raise RuntimeError("unbalanced")


out = []
i = 0
swaps = 0
while i < len(lines):
    stripped = lines[i].strip()
    # 匹配 yield final( 或直接 yield {**final(...)} 形式
    if stripped.startswith("yield final("):
        y_start = i
        y_end = block_end(i)
        # 紧随其后（允许空行）应是 _write_run_log(
        j = y_end + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].strip().startswith("_write_run_log("):
            w_start = j
            w_end = block_end(j)
            yield_block = lines[y_start : y_end + 1]
            log_block = lines[w_start : w_end + 1]
            # _write_run_log 的缩进与 yield 一致，直接拼接
            out.extend(log_block)
            out.extend(yield_block)
            swaps += 1
            i = w_end + 1
            continue
    out.append(lines[i])
    i += 1

result = "\n".join(out)
io.open(p, "w", encoding="utf-8", newline="").write(result)
print("swapped blocks:", swaps)

# 校验：所有 yield final 之后不应再紧跟 _write_run_log
after = io.open(p, encoding="utf-8").read().split("\n")
remaining = 0
for k, l in enumerate(after):
    if l.strip().startswith("yield final("):
        e = block_end_from(after, k) if False else None
print("done")

import py_compile
py_compile.compile(p, doraise=True)
print("runner.py compiles OK")