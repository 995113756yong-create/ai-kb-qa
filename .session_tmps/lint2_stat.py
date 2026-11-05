import json
import io

d = json.load(io.open("lint2.json", encoding="utf-8-sig"))
e = w = 0
for f in d:
    rel = f["filePath"].split("ai-kb-qa")[-1].replace("\\", "/")
    fe = [m for m in f["messages"] if m["severity"] == 2]
    fw = [m for m in f["messages"] if m["severity"] == 1]
    e += len(fe)
    w += len(fw)
    if fe:
        print("ERR", rel, [(m["line"], m.get("ruleId")) for m in fe])
    for m in fw:
        print("   warn", rel, m["line"], m.get("ruleId"), (m.get("message") or "")[:60])
print("TOTAL error =", e, " warning =", w)