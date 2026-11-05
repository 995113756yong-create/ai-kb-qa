import io

p = "README.md"
t = io.open(p, encoding="utf-8").read()

# ---- 1) 后端表：TRUST_PROXY 说明更新 + 新增 4 项 ----
old_trust = "| `TRUST_PROXY` | `false` | 是否信任 X-Forwarded-For（转发部署必须 true） |"
new_trust = (
    "| `TRUST_PROXY` | `false` | 是否信任 X-Forwarded-For（转发部署必须 true）。"
    "开启时取 XFF **最右侧**一项，左侧由客户端控制不可信 |"
)
assert old_trust in t, "TRUST_PROXY row not found"
t = t.replace(old_trust, new_trust, 1)

anchor_backend = "| `TOP_K` | `3` | 固定 RAG 的检索片段数 |"
assert anchor_backend in t
new_rows = anchor_backend + "\n" + "\n".join([
    "| `LLM_TIMEOUT_SECONDS` | `60` | 模型调用超时（秒）。流式回答是两 chunk 之间的读超时 |",
    "| `LLM_MAX_RETRIES` | `1` | 模型 / Embedding 调用失败重试次数上限 |",
    "| `EMBEDDING_TIMEOUT_SECONDS` | `30` | Embedding 调用超时（秒） |",
    "| `FEEDBACK_MAX_MB` | `5` | 反馈文件上限（MB），超过后轮转为 `feedback.jsonl.1` |",
])
t = t.replace(anchor_backend, new_rows, 1)

# ---- 2) 前端表：新增 TRUSTED_PROXY_HOPS ----
anchor_fe = "| `BACKEND_URL` | `http://localhost:8000` | 转发层的后端地址，**运行时**读取，可在部署时切换 |"
assert anchor_fe in t
new_fe = anchor_fe + "\n" + (
    "| `TRUSTED_PROXY_HOPS` | `1` | Next.js 前面会追加 XFF 的可信代理层数；"
    "限流只认右数第 N 项，左侧不可信 |"
)
t = t.replace(anchor_fe, new_fe, 1)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("README env tables updated")

lines = t.split("\n")
print("---- backend tail of table ----")
for i, l in enumerate(lines, 1):
    if "LLM_TIMEOUT_SECONDS" in l or "FEEDBACK_MAX_MB" in l or "TRUSTED_PROXY_HOPS" in l:
        print(f"{i}|{l[:110]}")