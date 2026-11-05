import io
import re

t = io.open("backend/.env", encoding="utf-8").read()
for line in t.split("\n"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    if "=" not in line:
        continue
    k, v = line.split("=", 1)
    k = k.strip()
    v = v.strip().strip('"').strip("'")
    if any(x in k.upper() for x in ("KEY", "TOKEN", "SECRET")):
        if not v:
            print(f"{k} = <空>")
        else:
            print(f"{k} = <已配置> 长度={len(v)}  前缀={v[:6]}...")
    else:
        print(f"{k} = {v}")