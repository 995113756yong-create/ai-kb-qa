import json
import io

d = json.load(io.open("lint.json", encoding="utf-8"))
tot_e = tot_w = 0
rows = []
for f in d:
    if not f["messages"]:
        continue
    e = sum(1 for m in f["messages"] if m["severity"] == 2)
    w = sum(1 for m in f["messages"] if m["severity"] == 1)
    tot_e += e
    tot_w += w
    rel = f["filePath"].split("ai-kb-qa")[-1].replace("\\", "/")
    if e:
        rows.append((e, w, rel))
rows.sort(reverse=True)
for e, w, rel in rows:
    print(f"E={e:<3} W={w:<3} {rel}")
print()
print("TOTAL error =", tot_e, " warning =", tot_w)
print()
print("=== errors by rule ===")
rule = {}
for f in d:
    for m in f["messages"]:
        if m["severity"] == 2:
            rule[m.get("ruleId")] = rule.get(m.get("ruleId"), 0) + 1
for k, v in sorted(rule.items(), key=lambda x: -x[1]):
    print(f"{v:<4} {k}")