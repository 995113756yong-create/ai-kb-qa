import io

p = "backend/app/agent/runner.py"
t = io.open(p, encoding="utf-8").read()

t = t.replace(
    "<<<<<<< HEAD\n    emit_phases: bool = False,\n=======\n    enable_intent: bool = False,\n>>>>>>> ab2caa7",
    "    emit_phases: bool = False,\n    enable_intent: bool = False,",
)

io.open(p, "w", encoding="utf-8", newline="").write(t)
left = sum(1 for l in t.split("\n") if l.startswith(("<<<<<<<", "=======", ">>>>>>>")))
print("runner.py resolved, markers left:", left)
