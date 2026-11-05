import io
import re

edits = [
    ("lib/useAgentRun.ts", [
        ('import type { AgentEvent, UsageInfo } from "@/lib/types";',
         'import type { AgentEvent } from "@/lib/types";'),
    ]),
    ("hooks/useHotkeys.ts", []),
    ("components/workspace/ExpertSwitcher.tsx", []),
    ("components/ui/alert-dialog.tsx", []),
]

for path, reps in edits:
    t = io.open(path, encoding="utf-8").read()
    for old, new in reps:
        if old in t:
            t = t.replace(old, new)
            print("replaced in", path)
    io.open(path, "w", encoding="utf-8", newline="").write(t)

# 逐个查看待删的声明行，供人工确认
for path, name in [
    ("lib/useAgentRun.ts", "_interactionMode"),
    ("hooks/useHotkeys.ts", "isTypingTarget"),
    ("components/workspace/ExpertSwitcher.tsx", "cn"),
    ("components/ui/alert-dialog.tsx", "buttonVariants"),
]:
    lines = io.open(path, encoding="utf-8").read().split("\n")
    print("####", path)
    for i, l in enumerate(lines, 1):
        if re.search(r"\b" + re.escape(name) + r"\b", l):
            print(f"  {i}|{l}")