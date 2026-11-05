import io

p = "frontend/components/ChatApp.tsx"
lines = io.open(p, encoding="utf-8").read().split("\n")

# 采用 HEAD（新架构）；theirs 仅在旧版 switch 里加 case "intent"，需迁到 useAgentRun.ts
out = []
i = 0
while i < len(lines):
    if lines[i].startswith("<<<<<<< HEAD"):
        i += 1
        ours = []
        while i < len(lines) and not lines[i].startswith("======="):
            ours.append(lines[i])
            i += 1
        i += 1
        while i < len(lines) and not lines[i].startswith(">>>>>>>"):
            i += 1
        i += 1
        out.extend(ours)
        continue
    out.append(lines[i])
    i += 1

io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
left = sum(1 for l in out if l.startswith(("<<<<<<<", "=======", ">>>>>>>")))
print("ChatApp.tsx resolved with HEAD, markers left:", left)
