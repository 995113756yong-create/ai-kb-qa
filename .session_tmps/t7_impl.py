import io

# ---- 1) config.py 新增 FEEDBACK_MAX_MB ----
p = "backend/app/config.py"
t = io.open(p, encoding="utf-8").read()
if "FEEDBACK_MAX_MB" not in t:
    t = t.rstrip("\n") + "\n" + (
        "\n# 反馈文件大小上限（MB）。/api/feedback 不需要鉴权、每条最大约 9.5KB，\n"
        "# 不设上限会无限增长；超过后轮转为 feedback.jsonl.1，磁盘最多占用约 2 倍上限。\n"
        'FEEDBACK_MAX_MB = float(os.getenv("FEEDBACK_MAX_MB", "5"))\n'
    )
    io.open(p, "w", encoding="utf-8", newline="").write(t)
    print("config.py: FEEDBACK_MAX_MB added")

# ---- 2) main.py 新增 _append_feedback ----
p = "backend/app/main.py"
t = io.open(p, encoding="utf-8").read()

old = '''            log_dir = store.log_dir_of(req.agent_id) if req.agent_id != DEFAULT_AGENT_ID else (
                agent_log_dir or config.AGENT_LOG_DIR)
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "feedback.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\\n")'''

new = '''            log_dir = store.log_dir_of(req.agent_id) if req.agent_id != DEFAULT_AGENT_ID else (
                agent_log_dir or config.AGENT_LOG_DIR)
            os.makedirs(log_dir, exist_ok=True)
            _append_feedback(
                os.path.join(log_dir, "feedback.jsonl"),
                json.dumps(entry, ensure_ascii=False) + "\\n",
                int(config.FEEDBACK_MAX_MB * 1024 * 1024),
            )'''

assert old in t, "feedback write block not found"
t = t.replace(old, new, 1)

# 在 submit_feedback 之前插入辅助函数
anchor = '''    @app.post("/api/feedback")'''
helper = '''    @app.post("/api/feedback")'''
insert_before = t.find(anchor)
assert insert_before > 0

helper_code = '''_feedback_lock = threading.Lock()


def _append_feedback(path: str, line: str, max_bytes: int) -> None:
    """追加一行反馈；超过上限时把当前文件轮转成 .1（覆盖旧的 .1）。

    磁盘占用最多约 2 倍上限：主文件 + 一个归档。
    """
    with _feedback_lock:
        if max_bytes > 0 and os.path.exists(path) and os.path.getsize(path) >= max_bytes:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


'''
# 插到模块级（在 create_app 之外），找到第一个 @app 装饰器之前不合适，
# 改为插在文件顶部的 import 之后
lines = t.split("\n")
last_import = 0
for i, l in enumerate(lines):
    if l.startswith("import ") or l.startswith("from "):
        last_import = i
lines.insert(last_import + 1, "\n" + helper_code.rstrip("\n"))
t = "\n".join(lines)

# 确保 threading 已导入
if "\nimport threading" not in t:
    t = t.replace("import os\n", "import os\nimport threading\n", 1)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("main.py: _append_feedback added")

import py_compile
py_compile.compile(p, doraise=True)
py_compile.compile("backend/app/config.py", doraise=True)
print("compiles OK")