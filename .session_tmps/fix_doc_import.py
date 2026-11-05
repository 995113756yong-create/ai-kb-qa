import io
import re

p = "backend/app/document.py"
t = io.open(p, encoding="utf-8").read()

# 把损坏的 import 块整体替换成正确的多行 import
bad_start = "from app.config import (, EMBEDDING_TIMEOUT_SECONDS, LLM_MAX_RETRIES"
idx = t.find(bad_start)
assert idx >= 0, "broken import not found"

# 收集原 import 的所有名字（从损坏块之后到右括号为止）
rest = t[idx + len(bad_start):]
end_rel = rest.find(")")
assert end_rel >= 0
inner = rest[:end_rel]
body = t[idx + len(bad_start) + end_rel + 1:]

names = []
for part in re.split(r"[,\n]", inner):
    part = part.strip()
    if part:
        names.append(part)

# 补上新增的两项
for extra in ("EMBEDDING_TIMEOUT_SECONDS", "LLM_MAX_RETRIES"):
    if extra not in names:
        names.append(extra)

names = sorted(set(names))
new_import = "from app.config import (\n" + "".join(f"    {n},\n" for n in names) + ")"
t = t[:idx] + new_import + body

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("fixed. names =", len(names))

# 校验能编译
import py_compile
py_compile.compile(p, doraise=True)
print("document.py compiles OK")

py_compile.compile("backend/app/qa.py", doraise=True)
py_compile.compile("backend/app/config.py", doraise=True)
py_compile.compile("backend/app/agent/llm.py", doraise=True)
print("qa.py / config.py / llm.py compile OK")