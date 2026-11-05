import io

# ---- qa.py: ChatOpenAI 加超时与重试 ----
p = "backend/app/qa.py"
t = io.open(p, encoding="utf-8").read()
old = """    return ChatOpenAI(
        model=CHAT_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
        temperature=0.1,
    )"""
new = """    return ChatOpenAI(
        model=CHAT_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
        temperature=0.1,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )"""
assert old in t, "qa.py ChatOpenAI block not found"
t = t.replace(old, new, 1)

# 补 import
if "LLM_TIMEOUT_SECONDS" not in t.split("def ")[0]:
    # 找到从 app.config import 的那一行并追加
    lines = t.split("\n")
    for i, l in enumerate(lines):
        if l.startswith("from app.config import") or l.startswith("from .config import"):
            names = [x.strip() for x in l.split("import", 1)[1].split(",")]
            if "LLM_TIMEOUT_SECONDS" not in names:
                names += ["LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES"]
                lines[i] = l.split("import")[0] + "import " + ", ".join(sorted(set(names)))
            break
    else:
        # 没有 config import，插到第一个 import 之后
        for i, l in enumerate(lines):
            if l.startswith("from app") or l.startswith("import "):
                lines.insert(i + 1, "from app.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS")
                break
    t = "\n".join(lines)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("qa.py updated")

# ---- document.py: OpenAIEmbeddings 加超时与重试 ----
p = "backend/app/document.py"
t = io.open(p, encoding="utf-8").read()
old = """    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
        check_embedding_ctx_length=False,
    )"""
new = """    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_BASE,
        check_embedding_ctx_length=False,
        timeout=EMBEDDING_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )"""
assert old in t, "document.py OpenAIEmbeddings block not found"
t = t.replace(old, new, 1)

lines = t.split("\n")
for i, l in enumerate(lines):
    if l.startswith("from app.config import") or l.startswith("from .config import"):
        prefix = l.split("import")[0]
        names = [x.strip() for x in l.split("import", 1)[1].split(",")]
        for extra in ("EMBEDDING_TIMEOUT_SECONDS", "LLM_MAX_RETRIES"):
            if extra not in names:
                names.append(extra)
        lines[i] = prefix + "import " + ", ".join(sorted(set(names)))
        break
t = "\n".join(lines)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("document.py updated")