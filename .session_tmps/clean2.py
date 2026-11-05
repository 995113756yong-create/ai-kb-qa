import io

# 1) useHotkeys.ts：删除未被调用的 isTypingTarget 函数
p = "hooks/useHotkeys.ts"
t = io.open(p, encoding="utf-8").read()
fn = '''function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.isContentEditable
  );
}

'''
assert fn in t, "isTypingTarget block not found"
t = t.replace(fn, "")
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("useHotkeys: removed isTypingTarget")

# 2) ExpertSwitcher.tsx：删除未使用的 cn 导入
p = "components/workspace/ExpertSwitcher.tsx"
t = io.open(p, encoding="utf-8").read()
line = 'import { cn } from "@/lib/utils";\n'
assert line in t
t = t.replace(line, "")
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("ExpertSwitcher: removed cn import")

# 3) alert-dialog.tsx：删除未使用的 buttonVariants 导入
p = "components/ui/alert-dialog.tsx"
t = io.open(p, encoding="utf-8").read()
line = 'import { buttonVariants } from "@/components/ui/button";\n'
assert line in t
t = t.replace(line, "")
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("alert-dialog: removed buttonVariants import")

# 4) useAgentRun.ts：_interactionMode 只是解构丢弃 mode，改成显式忽略写法
p = "lib/useAgentRun.ts"
t = io.open(p, encoding="utf-8").read()
old = "      const { mode: _interactionMode, answerMode, ...streamRest } = rest;"
new = "      const { mode: _ignoredMode, answerMode, ...streamRest } = rest;"
if old in t:
    t = t.replace(old, new)
    io.open(p, "w", encoding="utf-8", newline="").write(t)
    print("useAgentRun: renamed _interactionMode")