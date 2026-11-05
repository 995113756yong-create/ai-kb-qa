import io

t = io.open("frontend/lib/useAgentRun.ts", encoding="utf-8").read().split("\n")
for i, l in enumerate(t, 1):
    if "switch (event.type)" in l or l.strip().startswith("case "):
        print(i, "|", l)
print("---- phaseFromEvent 定义区 ----")
for i, l in enumerate(t, 1):
    if "phaseFromEvent" in l:
        print(i, "|", l)
