import subprocess

msg = """chore: 仓库卫生

- 删除 .session_tmps/（本次实施过程中 AI 工具生成的一次性脚本），并加入 .gitignore
- .gitignore 顺带忽略根目录误留的 lint.json / lint2.json
- README 项目结构补齐新增文件：security.py、intent.py、attribution.py、
  judge.py、calibrate_threshold.py、report.md、experts/、eval/、
  components/workspace/、components/ui/、hooks/、data/eval-summary.json、docs/
- docs/ui-revamp-progress.md 改为归档性质，去掉「PR 未创建」「Sealos 已停服」
  两条过时说明
- CI 升级 actions/checkout@v4 -> v5（3 处）、actions/setup-node@v4 -> v5（1 处），
  消除 Node 20 弃用警告
"""

subprocess.run(["git", "add", "-A"], check=True)
p = subprocess.run(
    ["git", "commit", "-F", "-"], input=msg, capture_output=True, text=True, encoding="utf-8"
)
print("exit", p.returncode)
print(p.stdout[-300:])
print(p.stderr[-200:])
