import subprocess

subprocess.run(["git", "add", "-A"], check=True)
p = subprocess.run(
    ["git", "commit", "-m", "chore: 移除误提交的临时脚本"],
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("commit exit", p.returncode)
print(p.stdout[-200:])

# 确认仓库里不再有临时文件
r = subprocess.run(
    ["git", "ls-files"], capture_output=True, text=True, encoding="utf-8"
)
leftovers = [
    l for l in r.stdout.splitlines()
    if ".session_tmps" in l or ".tmp_" in l or l.startswith("lint")
]
print("剩余临时文件:", leftovers if leftovers else "无")
