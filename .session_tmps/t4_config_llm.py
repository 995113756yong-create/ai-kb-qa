import io

# ---- 1) config.py 新增三项 ----
p = "backend/app/config.py"
t = io.open(p, encoding="utf-8").read()
if "LLM_TIMEOUT_SECONDS" not in t:
    t = t.rstrip("\n") + "\n" + (
        "\n# 模型调用超时（秒）。流式回答时是两个 chunk 之间的读超时，不是整段回答的总时长。\n"
        "# 不设上限时 SDK 默认 600 秒，模型服务一卡就会长时间占住后台线程。\n"
        'LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))\n'
        "# 模型调用失败重试次数上限（SDK 默认 2，模型服务抖动时容易叠加成长时间等待）\n"
        'LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))\n'
        "# Embedding 调用超时（秒）\n"
        'EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))\n'
    )
    io.open(p, "w", encoding="utf-8", newline="").write(t)
    print("config.py updated")
else:
    print("config.py already has LLM_TIMEOUT_SECONDS")

# ---- 2) agent/llm.py 给 OpenAI 客户端加超时与重试 ----
p = "backend/app/agent/llm.py"
t = io.open(p, encoding="utf-8").read()
old = """        self._client = OpenAI(
            api_key=api_key or config.OPENAI_API_KEY,
            base_url=base_url or config.OPENAI_API_BASE,
        )"""
new = """        self._client = OpenAI(
            api_key=api_key or config.OPENAI_API_KEY,
            base_url=base_url or config.OPENAI_API_BASE,
            timeout=config.LLM_TIMEOUT_SECONDS,
            max_retries=config.LLM_MAX_RETRIES,
        )"""
assert old in t, "llm.py OpenAI block not found"
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("llm.py updated")