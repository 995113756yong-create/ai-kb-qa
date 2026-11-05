import io
import json
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
base = env.get("OPENAI_API_BASE", "").rstrip("/")

for model_key in ("CHAT_MODEL", "AGENT_MODEL"):
    model = env.get(model_key, "")
    if not model:
        print(f"{model_key}: 未配置")
        continue
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "回复ok"}], "max_tokens": 16}
    ).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode())
            txt = d["choices"][0]["message"]["content"][:30]
            print(f"{model_key}={model}  OK -> {txt!r}")
    except urllib.error.HTTPError as e:
        print(f"{model_key}={model}  HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
    except Exception as e:
        print(f"{model_key}={model}  ERR {type(e).__name__}: {str(e)[:150]}")