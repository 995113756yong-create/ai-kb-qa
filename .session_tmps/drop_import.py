import io

p = "components/ChatApp.tsx"
t = io.open(p, encoding="utf-8").read()
line = 'import { useElapsed } from "@/hooks/useElapsed";\n'
assert line in t, "import line not found"
t = t.replace(line, "")
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("removed:", "useElapsed" not in t)