import io

# ---- 1) frontend/.env.example 增加 TRUSTED_PROXY_HOPS ----
p = "frontend/.env.example"
t = io.open(p, encoding="utf-8").read()
if "TRUSTED_PROXY_HOPS" not in t:
    if not t.endswith("\n"):
        t += "\n"
    t += (
        "# Next.js 前面会追加 X-Forwarded-For 的可信代理层数，默认 1\n"
        "# 限流只认右数第 N 项，左侧由客户端控制不可信\n"
        "TRUSTED_PROXY_HOPS=1\n"
    )
    io.open(p, "w", encoding="utf-8", newline="").write(t)
    print("frontend/.env.example updated")

# ---- 2) backend/.env.example 追加 T4 / T7 配置 ----
p = "backend/.env.example"
t = io.open(p, encoding="utf-8").read()
add = []
if "LLM_TIMEOUT_SECONDS" not in t:
    add.append(
        "# 模型调用超时（秒）。流式回答是两个 chunk 之间的读超时，不是整段总时长\n"
        "LLM_TIMEOUT_SECONDS=60\n"
        "# 模型调用失败重试次数上限\n"
        "LLM_MAX_RETRIES=1\n"
        "# Embedding 调用超时（秒）\n"
        "EMBEDDING_TIMEOUT_SECONDS=30"
    )
if "FEEDBACK_MAX_MB" not in t:
    add.append(
        "# 反馈文件大小上限（MB），超过后轮转为 feedback.jsonl.1\n"
        "FEEDBACK_MAX_MB=5"
    )
if add:
    if not t.endswith("\n"):
        t += "\n"
    t += "\n" + "\n\n".join(add) + "\n"
    io.open(p, "w", encoding="utf-8", newline="").write(t)
    print("backend/.env.example updated")

print("---- frontend/.env.example ----")
print(io.open("frontend/.env.example", encoding="utf-8").read())
print("---- backend tail ----")
lines = io.open("backend/.env.example", encoding="utf-8").read().split("\n")
print("\n".join(lines[-12:]))