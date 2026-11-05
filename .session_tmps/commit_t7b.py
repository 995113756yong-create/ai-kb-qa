import subprocess

msg = """fix: 反馈文件超过上限时轮转

/api/feedback 不需要鉴权且每条最大约 9.5KB, 原先一直追加写入 feedback.jsonl,
文件大小没有上限.

- config 新增 FEEDBACK_MAX_MB(5)
- main.py 新增 _append_feedback: 超过上限时把当前文件轮转为 .1 (覆盖旧的 .1),
  磁盘占用最多约 2 倍上限; 带 threading.Lock, 多线程并发写不丢行
- .env.example 与 README 环境变量表同步

测试: 新增 test_feedback_rotation.py 3 项.
注意: agent_log_dir 是 create_app 的默认参数, 只在定义时求值, 测试需显式传入.
"""

subprocess.run(["git", "add", "-A"], check=True)
p = subprocess.run(
    ["git", "commit", "-F", "-"],
    input=msg,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("exit", p.returncode)
print(p.stdout[-400:])
print(p.stderr[-300:])
