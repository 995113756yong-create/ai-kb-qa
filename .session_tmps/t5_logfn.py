import io

p = "backend/app/agent/runner.py"
t = io.open(p, encoding="utf-8").read()

old_sig = '''def _write_run_log(
    log_dir: Optional[str],
    question: str,
    steps: List[dict],
    registry: EvidenceRegistry,
    answer: str,
    grounded: bool,
    elapsed_ms: int,
    error: Optional[str] = None,
    mode: str = "",
    grounded_ratio: Optional[float] = None,
    numeric_warnings: int = 0,
    usage: Optional[dict] = None,
    intent: str = "",
) -> None:'''

new_sig = '''def _write_run_log(
    log_dir: Optional[str],
    question: str,
    steps: List[dict],
    registry: Optional[EvidenceRegistry],
    answer: str,
    grounded: bool,
    elapsed_ms: int,
    error: Optional[str] = None,
    mode: str = "",
    grounded_ratio: Optional[float] = None,
    numeric_warnings: int = 0,
    usage: Optional[dict] = None,
    intent: str = "",
    stopped: bool = False,
) -> None:'''

assert old_sig in t, "signature not found"
t = t.replace(old_sig, new_sig, 1)

old_body = '''    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "steps": steps,
        "evidence_count": len(registry),'''

new_body = '''    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "steps": steps,
        "evidence_count": len(registry) if registry is not None else None,'''

assert old_body in t, "record block not found"
t = t.replace(old_body, new_body, 1)

# stopped 为 False 时不写该字段，保持既有日志结构与测试不变
old_tail = '''    if error:
        record["error"] = error'''
new_tail = '''    if stopped:
        # 只有被用户停止 / 断连时才写这个字段，正常结束的日志结构保持不变
        record["stopped"] = True
    if error:
        record["error"] = error'''
assert old_tail in t, "error block not found"
t = t.replace(old_tail, new_tail, 1)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("_write_run_log updated")

import py_compile
py_compile.compile(p, doraise=True)
print("runner.py compiles OK")