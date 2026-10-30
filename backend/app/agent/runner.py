"""手写 ReAct 循环：研究阶段调用工具收集证据，回答阶段流式输出并校验引用。"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Iterator, List, Optional

from app.config import AGENT_LOG_DIR, AGENT_MAX_STEPS, AGENT_SEARCH_K
from app.document import KnowledgeBase
from app.agent.evidence import EvidenceRegistry
from app.agent.llm import AgentLLM, AssistantTurn
from app.agent.prompts import ANSWER_PROMPT, SYSTEM_PROMPT
from app.agent.query_rewrite import decompose_question, should_attempt_decompose
from app.qa import EMPTY_KB_ANSWER, NOT_FOUND_ANSWER
from app.agent.tools import TOOL_SCHEMAS, execute_tool, summarize, to_text

logger = logging.getLogger(__name__)

LOG_FILE = "agent_runs.jsonl"
MAX_CONSECUTIVE_ERRORS = 3


def final(answer: str, sources: List[dict], grounded: bool, steps: int, elapsed_ms: int) -> dict:
    return {
        "type": "final",
        "answer": answer,
        "sources": sources,
        "grounded": grounded,
        "steps": steps,
        "elapsed_ms": elapsed_ms,
    }


def assistant_message(turn: AssistantTurn) -> dict:
    """回填给模型的 assistant 消息必须原样带上 tool_calls，否则下一轮会报错。"""
    return {
        "role": "assistant",
        "content": turn.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in turn.tool_calls
        ],
    }


def canonical_json(raw_arguments: str) -> str:
    """参数顺序不同但语义相同的调用视为重复，用规范化 JSON 做键。"""
    try:
        return json.dumps(json.loads(raw_arguments or "{}"), sort_keys=True, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return (raw_arguments or "").strip()


def safe_parse(raw_arguments: str) -> dict:
    """透给前端展示的参数；解析不出来就原样给出，不因为展示影响流程。"""
    try:
        parsed = json.loads(raw_arguments or "{}")
    except (json.JSONDecodeError, TypeError):
        return {"_raw": raw_arguments}
    return parsed if isinstance(parsed, dict) else {"_raw": raw_arguments}


def answer_messages(question: str, registry: EvidenceRegistry) -> List[dict]:
    return [
        {"role": "system", "content": ANSWER_PROMPT},
        {
            "role": "user",
            "content": f"证据：\n\n{registry.format_for_prompt()}\n\n问题：{question}",
        },
    ]


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
) -> Iterator[dict]:
    """产出事件流的同步生成器，由 SSE 层包装成异步响应。

    enable_decompose / enable_rerank 默认关闭，调用方（通常是 main.py 的生产路径）
    按配置显式打开。decompose_llm / rerank_llm 不传时复用主 llm。
    """
    started = time.monotonic()
    registry = EvidenceRegistry()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    seen_calls: set = set()
    consecutive_errors = 0
    steps: List[dict] = []
    step = 0
    effective_rerank_llm = (rerank_llm or llm) if enable_rerank else None

    def elapsed() -> int:
        return int((time.monotonic() - started) * 1000)

    if kb.is_empty:
        yield final(EMPTY_KB_ANSWER, [], True, 0, elapsed())
        return

    try:
        if enable_decompose and should_attempt_decompose(question):
            sub_queries = decompose_question(decompose_llm or llm, question)
            if len(sub_queries) > 1:
                yield {"type": "decompose", "step": 0, "queries": sub_queries}
                for i, sub_q in enumerate(sub_queries, start=1):
                    call_id = f"decomp-{i}"
                    call_args = json.dumps({"query": sub_q}, ensure_ascii=False)
                    yield {
                        "type": "tool_call",
                        "step": 0,
                        "id": call_id,
                        "name": "search_kb",
                        "args": {"query": sub_q},
                    }
                    result = execute_tool(
                        "search_kb", call_args, kb, registry,
                        search_k=search_k, rerank_llm=effective_rerank_llm,
                    )
                    ok = "error" not in result
                    yield {
                        "type": "tool_result",
                        "step": 0,
                        "id": call_id,
                        "name": "search_kb",
                        "ok": ok,
                        "summary": summarize(result),
                    }
                    steps.append(
                        {
                            "step": 0,
                            "tool": "search_kb",
                            "args": {"query": sub_q},
                            "ok": ok,
                            "summary": summarize(result),
                        }
                    )
                    # 预检索过的查询记入去重表，模型后面原样再查时直接短路，不重复花钱
                    seen_calls.add(f"search_kb:{canonical_json(call_args)}")

        for step in range(1, max_steps + 1):
            yield {"type": "step", "step": step}
            turn = llm.chat(messages, tools=TOOL_SCHEMAS)
            if turn.content:
                yield {"type": "thought", "step": step, "text": turn.content}
            if not turn.tool_calls:
                break  # 模型认为信息足够了

            messages.append(assistant_message(turn))
            for call in turn.tool_calls:
                key = f"{call.name}:{canonical_json(call.arguments)}"
                yield {
                    "type": "tool_call",
                    "step": step,
                    "id": call.id,
                    "name": call.name,
                    "args": safe_parse(call.arguments),
                }
                if key in seen_calls:
                    result = {"error": "与之前的调用完全相同，结果同上。请换关键词或开始回答。"}
                else:
                    seen_calls.add(key)
                    result = execute_tool(
                        call.name, call.arguments, kb, registry,
                        search_k=search_k, rerank_llm=effective_rerank_llm,
                    )

                ok = "error" not in result
                consecutive_errors = 0 if ok else consecutive_errors + 1
                summary = summarize(result)
                yield {
                    "type": "tool_result",
                    "step": step,
                    "id": call.id,
                    "name": call.name,
                    "ok": ok,
                    "summary": summary,
                }
                steps.append(
                    {
                        "step": step,
                        "tool": call.name,
                        "args": safe_parse(call.arguments),
                        "ok": ok,
                        "summary": summary,
                    }
                )
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": to_text(result)}
                )
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                break
        # 达到最大步数时同样进入回答阶段，不再调用工具

        if registry.is_empty():
            answer = NOT_FOUND_ANSWER
            yield final(answer, [], True, step, elapsed())
            _write_run_log(log_dir, question, steps, registry, answer, True, elapsed())
            return

        raw = ""
        for delta in llm.stream(answer_messages(question, registry)):
            raw += delta
            yield {"type": "answer_delta", "text": delta}

        answer, sources, grounded = registry.finalize(raw)
        used_ms = elapsed()
        yield final(answer, sources, grounded, step, used_ms)
        _write_run_log(log_dir, question, steps, registry, answer, grounded, used_ms)
    except Exception as e:
        # API Key 和堆栈只进服务端日志，前端只看到一句人话
        logger.exception("Agent 运行失败")
        yield {"type": "error", "detail": f"大模型调用失败：{type(e).__name__}"}
        _write_run_log(log_dir, question, steps, registry, "", False, elapsed(), error=str(e))


def _write_run_log(
    log_dir: Optional[str],
    question: str,
    steps: List[dict],
    registry: EvidenceRegistry,
    answer: str,
    grounded: bool,
    elapsed_ms: int,
    error: Optional[str] = None,
) -> None:
    """追加一行运行记录，供后续评测离线分析；写失败不影响响应。"""
    if not log_dir:
        return
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "steps": steps,
        "evidence_count": len(registry),
        "answer": answer,
        "grounded": grounded,
        "elapsed_ms": elapsed_ms,
    }
    if error:
        record["error"] = error
    try:
        import os

        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, LOG_FILE), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning("写 Agent 运行日志失败：%s", e)
