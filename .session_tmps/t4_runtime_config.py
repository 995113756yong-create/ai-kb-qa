import io

# qa.py：改为运行时读 config，避免 import 绑定导致配置不可覆盖
p = "backend/app/qa.py"
t = io.open(p, encoding="utf-8").read()
t = t.replace(
    "from app.config import CHAT_MODEL, LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS, OPENAI_API_BASE, OPENAI_API_KEY, TOP_K",
    "from app import config\nfrom app.config import CHAT_MODEL, OPENAI_API_BASE, OPENAI_API_KEY, TOP_K",
)
t = t.replace("        timeout=LLM_TIMEOUT_SECONDS,", "        timeout=config.LLM_TIMEOUT_SECONDS,")
t = t.replace("        max_retries=LLM_MAX_RETRIES,", "        max_retries=config.LLM_MAX_RETRIES,")
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("qa.py -> runtime config lookup")

# document.py：同样处理
p = "backend/app/document.py"
t = io.open(p, encoding="utf-8").read()
t = t.replace("    EMBEDDING_TIMEOUT_SECONDS,\n", "")
t = t.replace("    LLM_MAX_RETRIES,\n", "")
if "from app import config" not in t:
    t = t.replace("from app.config import (", "from app import config\nfrom app.config import (", 1)
t = t.replace("        timeout=EMBEDDING_TIMEOUT_SECONDS,", "        timeout=config.EMBEDDING_TIMEOUT_SECONDS,")
t = t.replace("        max_retries=LLM_MAX_RETRIES,", "        max_retries=config.LLM_MAX_RETRIES,")
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("document.py -> runtime config lookup")

import py_compile
for f in ("backend/app/qa.py", "backend/app/document.py"):
    py_compile.compile(f, doraise=True)
    print(f, "compiles OK")