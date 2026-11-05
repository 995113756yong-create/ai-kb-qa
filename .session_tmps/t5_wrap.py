import io

p = "backend/app/agent/runner.py"
t = io.open(p, encoding="utf-8").read()

# 1) 原函数改名为 _run_agent_impl（函数体一行不动）
old_sig = '''def run_agent(
    question: str,
    kb: KnowledgeBase,
    llm: AgentLLM,
    max_steps: int = AGENT_MAX_STEPS,
    log_dir: Optional[str] = AGENT_LOG_DIR,
    search_k: int = AGENT_SEARCH_K,
    enable_decompose: bool = False,
    enable_rerank: bool = False,
    decompose_llm: Optional[AgentLLM] = None,
    rerank_llm: Optional[AgentLLM] = None,
    persona: str = "",
    agent_id: str = "",
    answer_mode: str = "reference",
    emit_phases: bool = False,
    enable_intent: bool = False,
) -> Iterator[dict]:'''

new_sig = '''def _run_agent_impl(
    question: str,
    kb: KnowledgeBase,
    llm: AgentLLM,
    max_steps: int = AGENT_MAX_STEPS,
    log_dir: Optional[str] = AGENT_LOG_DIR,
    search_k: int = AGENT_SEARCH_K,
    enable_decompose: bool = False,
    enable_rerank: bool = False,
    decompose_llm: Optional[AgentLLM] = None,
    rerank_llm: Optional[AgentLLM] = None,
    persona: str = "",
    agent_id: str = "",
    answer_mode: str = "reference",
    emit_phases: bool = False,
    enable_intent: bool = False,
) -> Iterator[dict]:'''

assert old_sig in t, "run_agent signature not found"
t = t.replace(old_sig, new_sig, 1)

# 2) 找到 _run_agent_impl 结束位置（下一个顶层 def 之前），插入新的 run_agent 包装
marker = "\ndef _write_run_log("
idx = t.find(marker)
assert idx > 0, "insert anchor not found"

wrapper = '''

def run_agent(
    question: str,
    kb: KnowledgeBase,
    llm: AgentLLM,
    max_steps: int = AGENT_MAX_STEPS,
    log_dir: Optional[str] = AGENT_LOG_DIR,
    search_k: int = AGENT_SEARCH_K,
    enable_decompose: bool = False,
    enable_rerank: bool = False,
    decompose_llm: Optional[AgentLLM] = None,
    rerank_llm: Optional[AgentLLM] = None,
    persona: str = "",
    agent_id: str = "",
    answer_mode: str = "reference",
    emit_phases: bool = False,
    enable_intent: bool = False,
) -> Iterator[dict]:
    """对外入口。用户停止或断连时（生成器被 close），补写一条 stopped 运行日志。

    正常结束和异常结束的日志由 _run_agent_impl 在发出 final / error 事件之前写好，
    这里只负责中途被关闭的情况，因此不会写重。
    """
    started = time.monotonic()
    inner = _run_agent_impl(
        question,
        kb,
        llm,
        max_steps=max_steps,
        log_dir=log_dir,
        search_k=search_k,
        enable_decompose=enable_decompose,
        enable_rerank=enable_rerank,
        decompose_llm=decompose_llm,
        rerank_llm=rerank_llm,
        persona=persona,
        agent_id=agent_id,
        answer_mode=answer_mode,
        emit_phases=emit_phases,
        enable_intent=enable_intent,
    )
    finished = False
    partial: List[str] = []
    calls: List[dict] = []
    try:
        for event in inner:
            etype = event.get("type")
            if etype in ("final", "error"):
                finished = True
            elif etype == "answer_delta":
                partial.append(event.get("text") or "")
            elif etype == "tool_call":
                calls.append(
                    {"step": event.get("step"), "tool": event.get("name"), "args": event.get("args")}
                )
            yield event
    except GeneratorExit:
        inner.close()
        if not finished:
            _write_run_log(
                log_dir,
                question,
                calls,
                None,
                "".join(partial),
                False,
                int((time.monotonic() - started) * 1000),
                mode=answer_mode,
                stopped=True,
            )
        raise

'''

t = t[:idx] + wrapper + t[idx:]
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("run_agent wrapped")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")