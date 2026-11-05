import json
import io

d = json.load(io.open("lint.json", encoding="utf-8"))
for f in d:
    rel = f["filePath"].split("ai-kb-qa")[-1].replace("\\", "/")
    errs = [m for m in f["messages"] if m["severity"] == 2]
    if not errs:
        continue
    print("#" * 10, rel)
    for m in errs:
        print(f"  L{m['line']}:{m['column']}  {m.get('ruleId')}")
        print(f"     {m.get('message', '').splitlines()[0][:150]}")
    print()