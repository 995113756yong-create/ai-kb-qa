import io
import json
import os
import urllib.request

t = io.open("backend/.env", encoding="utf-8").read()
env = {}
for line in t.split("\n"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

key = env.get("OPENAI_API_KEY", "")
base = env.get("OPENAI_API_BASE", "https://api.siliconflow.cn/v1").rstrip("/")

# 1) 用 embedding 接口做一次最小调用，成本几乎为零
body = json.dumps(
    {"model": env.get("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"), "input": "ping"}
).encode()
req = urllib.request.Request(
    f"{base}/embeddings",
    data=body,
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
        n = len(d.get("data", [{}])[0].get("embedding", []))
        print(f"OK  status={r.status}  embedding_dim={n}")
except urllib.error.HTTPError as e:
    msg = e.read().decode(errors="replace")[:300]
    print(f"HTTP {e.code}: {msg}")
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:200])