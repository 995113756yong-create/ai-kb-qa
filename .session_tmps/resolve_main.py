import io

p = "backend/app/main.py"
t = io.open(p, encoding="utf-8").read()

lines = t.split("\n")
out = []
i = 0
while i < len(lines):
    if lines[i].startswith("<<<<<<< HEAD"):
        # 收集 ours / theirs
        i += 1
        ours = []
        while i < len(lines) and not lines[i].startswith("======="):
            ours.append(lines[i])
            i += 1
        i += 1
        theirs = []
        while i < len(lines) and not lines[i].startswith(">>>>>>>"):
            theirs.append(lines[i])
            i += 1
        i += 1
        out.extend(ours)
        out.extend(theirs)
        continue
    out.append(lines[i])
    i += 1

io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
print("resolved, remaining markers:", sum(1 for l in out if l.startswith(("<<<<<<<", "=======", ">>>>>>>"))))
