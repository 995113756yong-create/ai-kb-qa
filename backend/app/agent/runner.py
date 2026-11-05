"""手写 ReAct 循环：研究阶段调用工具收集证据，回答阶段流式输出并校验引用。"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Iterator, List, Optional

from app.config import AGENT_LOG_DIR, AGENT_MAX_STEPS, AGENT_SEARCH_K
from app.document import KnowledgeBase
from app.agent.attribution import Attribution, attribute
from app.agent.evidence import EvidenceRegistry
from app.agent.llm import AgentLLM, AssistantTurn, Usage
from app.agent.prompts import (
    CHAT_PROMPT,
    NO_EVIDENCE_ANSWER_PROMPT,
    RESEARCH_PROMPT_REFERENCE,
    RESEARCH_PROMPT_STRICT,
    REFERENCE_ANSWER_PROMPT,
    STRICT_ANSWER_PROMPT,
    VALID_MODES,
    with_persona,
)
from app.agent.query_rewrite import decompose_question, should_attempt_decompose
from app.agent.intent import CHAT, KB_QUERY, LIST_DOCS, classify
from app.qa import EMPTY_KB_ANSWER, NOT_FOUND_ANSWER
from app.agent.tools import TOOL_SCHEMAS, execute_tool, summarize, to_text

logger = logging.getLogger(__name__)

LOG_FILE = "agent_runs.jsonl"
MAX_CONSECUTIVE_ERRORS = 3


class _UsageMeter:
    """累加一次 run_agent 全程的 token 用量与调用次数。"""

    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.llm_calls = 0
        self.usage: Optional[Usage] = None

    def add(self, usage: Optional[Usage]) -> None:
        if usage is None:
            return
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens

    def snapshot(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "llm_calls": self.llm_calls,
        }


class MeteredLLM:
    """包装 AgentLLM，统计 chat/stream 的调用次数与 token 用量。

    stream 可能 yield Usage 对象（LLM_STREAM_USAGE 开启时流末尾），
    这里把 Usage 累加进 meter、只向上转发字符串增量——
    run_agent 的流式拼接逻辑完全不感知 Usage。
    """

    def __init__(self, inner: AgentLLM, meter: _UsageMeter):
        self._inner = inner
        self._meter = meter

    def chat(self, messages, tools=None):
        self._meter.llm_calls += 1
        turn = self._inner.chat(messages, tools=tools)
        self._meter.add(turn.usage)
        return turn

    def stream(self, messages):
        self._meter.llm_calls += 1
        for item in self._inner.stream(messages):
            if isinstance(item, Usage):
                self._meter.add(item)
                continue
            if isinstance(item, str):
                yield item


def final(
    answer: str,
    sources: List[dict],
    grounded: bool,
    steps: int,
    elapsed_ms: int,
    agent_id: str = "",
    mode: str = "",
    grounded_ratio: Optional[float] = None,
    segments: Optional[List[dict]] = None,
    usage: Optional[dict] = None,
) -> dict:
    event = {
        "type": "final",
        "answer": answer,
        "sources": sources,
        "grounded": grounded,
        "steps": steps,
        "elapsed_ms": elapsed_ms,
    }
    if agent_id:
        event["agent_id"] = agent_id
    if mode:
        event["mode"] = mode
    # grounded_ratio 为 None 时也输出（前端靠 null 区分"无意义"和"全 neutral"）
    if mode:
        event["grounded_ratio"] = grounded_ratio
        event["segments"] = segments or []
    if usage is not None:
        event["usage"] = usage
    return event


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


def _answer_messages_no_evidence(question: str, mode: str = "reference", persona: str = "") -> List[dict]:
    """知识库无可用证据时的回答消息: reference 模式让模型用自己的知识回答并声明来源."""
    prompt = with_persona(NO_EVIDENCE_ANSWER_PROMPT, persona)
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ]


def _answer_without_evidence(
    question: str,
    llm: AgentLLM,
    registry: EvidenceRegistry,
    agent_id: str,
    elapsed,
    log_dir: Optional[str],
    steps: List[dict],
    done_step: int = 0,
    mode: str = "reference",
    persona: str = "",
    meter: Optional[_UsageMeter] = None,
):
    """无证据兜底回答（reference 模式）：模型自身知识回答 + attribution 标注.

    供两处复用: 知识库为空 / 检索多轮无相关证据.
    """
    raw = ""
    try:
        for delta in llm.stream(_answer_messages_no_evidence(question, mode, persona)):
            raw += delta
            yield {"type": "answer_delta", "text": delta}
    except Exception as e:
        logger.exception("无证据回答失败")
        yield {"type": "error", "detail": f"大模型调用失败：{type(e).__name__}"}
        return
    answer = raw.strip() or "这个问题我暂时答不上来。"
    att = attribute(answer, [], question)
    used_ms = elapsed()
    yield final(
        answer,
        [],
        att.grounded,
        done_step,
        used_ms,
        agent_id,
        mode=mode,
        grounded_ratio=att.grounded_ratio,
        segments=_segments_payload(att),
        usage=meter.snapshot() if meter else None,
    )
    _write_run_log(
        log_dir, question, steps, registry, answer, att.grounded, used_ms,
        mode=mode, grounded_ratio=att.grounded_ratio,
        numeric_warnings=att.numeric_warnings,
        usage=meter.snapshot() if meter else None,
    )


def _answer_chat(
    question: str,
    llm: AgentLLM,
    registry: EvidenceRegistry,
    agent_id: str,
    elapsed,
    log_dir: Optional[str],
    steps: List[dict],
    mode: str = "reference",
    persona: str = "",
    meter: Optional[_UsageMeter] = None,
):
    """闲聊分流：不带工具、不检索，一次流式调用直接回复。"""
    messages = [
        {"role": "system", "content": with_persona(CHAT_PROMPT, persona)},
        {"role": "user", "content": question},
    ]
    raw = ""
    try:
        for delta in llm.stream(messages):
            raw += delta
            yield {"type": "answer_delta", "text": delta}
    except Exception as e:
        logger.exception("闲聊回复失败")
        yield {"type": "error", "detail": f"大模型调用失败：{type(e).__name__}"}
        return
    answer = raw.strip() or "你好，有什么可以帮你？"
    used_ms = elapsed()
    usage = meter.snapshot() if meter else None
    yield final(answer, [], True, 0, used_ms, agent_id, mode=mode,
                grounded_ratio=None, segments=[], usage=usage)
    _write_run_log(log_dir, question, steps, registry, answer, True, used_ms,
                   mode=mode, grounded_ratio=None, usage=usage, intent=CHAT)


def _answer_list_docs(
    question: str,
    kb: KnowledgeBase,
    registry: EvidenceRegistry,
    agent_id: str,
    elapsed,
    log_dir: Optional[str],
    steps: List[dict],
    mode: str = "reference",
    meter: Optional[_UsageMeter] = None,
):
    """列文档分流：直接调用 list_documents 工具，用模板拼回答，不调用大模型。"""
    call_args = "{}"
    yield {"type": "tool_call", "step": 0, "id": "intent-list", "name": "list_documents", "args": {}}
    result = execute_tool("list_documents", call_args, kb, registry)
    ok = "error" not in result
    summary = summarize(result)
    yield {"type": "tool_result", "step": 0, "id": "intent-list", "name": "list_documents",
           "ok": ok, "summary": summary}
    steps.append({"step": 0, "tool": "list_documents", "args": {}, "ok": ok, "summary": summary})

    items = result.get("items") or []
    if not items:
        answer = "知识库目前是空的，还没有上传任何文档。"
    else:
        lines = [f"知识库中共有 {len(items)} 个文档："]
        lines += [f"- {d['filename']}（{d['chunks']} 个片段）" for d in items]
        answer = "\n".join(lines)
    yield {"type": "answer_delta", "text": answer}
    used_ms = elapsed()
    usage = meter.snapshot() if meter else None
    yield final(answer, [], True, 0, used_ms, agent_id, mode=mode,
                grounded_ratio=None, segments=[], usage=usage)
    _write_run_log(log_dir, question, steps, registry, answer, True, used_ms,
                   mode=mode, grounded_ratio=None, usage=usage, intent=LIST_DOCS)


def answer_messages(
    question: str,
    registry: EvidenceRegistry,
    mode: str = "reference",
    persona: str = "",
) -> List[dict]:
    base = STRICT_ANSWER_PROMPT if mode == "strict" else REFERENCE_ANSWER_PROMPT
    return [
        {"role": "system", "content": with_persona(base, persona)},
        {
            "role": "user",
            "content": f"证据：\n\n{registry.format_for_prompt()}\n\n问题：{question}",
        },
    ]


def _segments_payload(att: Attribution) -> List[dict]:
    return [
        {
            "text": s.text,
            "kind": s.kind,
            "citations": s.citations,
            "warnings": s.warnings,
        }
        for s in att.segments
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
    persona: str = "",
    agent_id: str = "",
    answer_mode: str = "reference",
    emit_phases: bool = False,
    enable_intent: bool = False,
) -> Iterator[dict]:
    """产出事件流的同步生成器，由 SSE 层包装成异步响应。

    enable_decompose / enable_rerank 默认关闭，调用方（通常是 main.py 的生产路径）
    按配置显式打开。decompose_llm / rerank_llm 不传时复用主 llm。

    persona 是专家人设（多专家平台用）：非空时拼进 system prompt，
    决定这个专家「怎么说话」；检索与引用校验的行为完全不变。
    agent_id 只用于 final 事件回带与运行日志区分，空串即旧行为。
    """
    if answer_mode not in VALID_MODES:
        raise ValueError(f"answer_mode 必须是 {VALID_MODES} 之一，收到 {answer_mode!r}")

    started = time.monotonic()
    registry = EvidenceRegistry()
    meter = _UsageMeter()
    llm = MeteredLLM(llm, meter)
    effective_decompose_llm = MeteredLLM(decompose_llm, meter) if decompose_llm else None
    effective_rerank_llm = (
        MeteredLLM(rerank_llm, meter) if (enable_rerank and rerank_llm) else None
    )

    base_research = RESEARCH_PROMPT_STRICT if answer_mode == "strict" else RESEARCH_PROMPT_REFERENCE
    messages = [
        {"role": "system", "content": with_persona(base_research, persona)},
        {"role": "user", "content": question},
    ]
    seen_calls: set = set()
    consecutive_errors = 0
    steps: List[dict] = []
    step = 0

    def elapsed() -> int:
        return int((time.monotonic() - started) * 1000)

    intent = None
    if enable_intent:
        intent = classify(question)
        yield {"type": "intent", "intent": intent.intent, "reason": intent.reason}
        if intent.intent == CHAT:
            yield from _answer_chat(question, llm, registry, agent_id, elapsed, log_dir, steps,
                                    mode=answer_mode, persona=persona, meter=meter)
            return
        if intent.intent == LIST_DOCS:
            yield from _answer_list_docs(question, kb, registry, agent_id, elapsed, log_dir, steps,
                                         mode=answer_mode, meter=meter)
            return

    if kb.is_empty:
        if answer_mode == "strict":
            # strict 模式：知识库为空就是没有依据，输出固定话术
            yield {"type": "answer_delta", "text": NOT_FOUND_ANSWER}
            yield final(NOT_FOUND_ANSWER, [], True, 0, elapsed(), agent_id, mode="strict",
                        grounded_ratio=None, segments=[], usage=meter.snapshot())
            _write_run_log(log_dir, question, steps, registry, NOT_FOUND_ANSWER, True, elapsed(),
                           mode="strict", grounded_ratio=None, numeric_warnings=0,
                           usage=meter.snapshot())
            return
        # reference：模型自身知识回答 + attribution
        yield from _answer_without_evidence(
            question, llm, registry, agent_id, elapsed, log_dir, steps,
            mode=answer_mode, persona=persona, meter=meter,
        )
        return

    try:
        if intent is not None and intent.intent == KB_QUERY:
            call_id = "intent-1"
            call_args = json.dumps({"query": question}, ensure_ascii=False)
            yield {"type": "tool_call", "step": 0, "id": call_id, "name": "search_kb",
                   "args": {"query": question}}
            result = execute_tool("search_kb", call_args, kb, registry,
                                  search_k=search_k, rerank_llm=effective_rerank_llm)
            ok = "error" not in result
            summary = summarize(result)
            yield {"type": "tool_result", "step": 0, "id": call_id, "name": "search_kb",
                   "ok": ok, "summary": summary}
            steps.append({"step": 0, "tool": "search_kb", "args": {"query": question},
                          "ok": ok, "summary": summary})
            # 预检索结果交给模型作参考：模型能看到已查过什么，原样再查会被去重短路
            seen_calls.add(f"search_kb:{canonical_json(call_args)}")
            if ok:
                messages.append({
                    "role": "user",
                    "content": "（系统已用原问题预先检索了一次，结果如下，可直接引用其中的证据编号；"
                               "不够再换关键词检索。）\n" + to_text(result),
                })

        if enable_decompose and should_attempt_decompose(question):
            sub_queries = decompose_question(effective_decompose_llm or llm, question)
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
                    hits = result.pop("hits", None)
                    event = {
                        "type": "tool_result",
                        "step": 0,
                        "id": call_id,
                        "name": "search_kb",
                        "ok": ok,
                        "summary": summarize(result),
                    }
                    if hits:
                        event["hits"] = hits
                    yield event
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

        if emit_phases:
            yield {"type": "phase", "phase": "research"}
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
                hits = result.pop("hits", None)
                summary = summarize(result)
                event = {
                    "type": "tool_result",
                    "step": step,
                    "id": call.id,
                    "name": call.name,
                    "ok": ok,
                    "summary": summary,
                }
                if hits:
                    event["hits"] = hits
                yield event
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
        if emit_phases:
            yield {"type": "phase", "phase": "answer"}

        if registry.is_empty():
            if answer_mode == "strict":
                # strict：检索无果即无依据，输出固定话术拒答
                yield {"type": "answer_delta", "text": NOT_FOUND_ANSWER}
                yield final(NOT_FOUND_ANSWER, [], True, step, elapsed(), agent_id, mode="strict",
                            grounded_ratio=None, segments=[], usage=meter.snapshot())
                _write_run_log(log_dir, question, steps, registry, NOT_FOUND_ANSWER, True, elapsed(),
                               mode="strict", grounded_ratio=None, numeric_warnings=0,
                               usage=meter.snapshot())
                return
            # reference：兜底回答 + attribution
            yield from _answer_without_evidence(
                question, llm, registry, agent_id, elapsed, log_dir, steps,
                done_step=step, mode=answer_mode, persona=persona, meter=meter,
            )
            return

        raw = ""
        for delta in llm.stream(answer_messages(question, registry, answer_mode, persona)):
            raw += delta
            yield {"type": "answer_delta", "text": delta}

        answer, sources, grounded = registry.finalize(raw)
        used_ms = elapsed()
        att = attribute(answer, sources, question)
        if answer_mode == "strict" and answer.strip() == NOT_FOUND_ANSWER:
            # strict 模式下的合规拒答：有依据比例无意义
            yield final(answer, sources, True, step, used_ms, agent_id, mode="strict",
                        grounded_ratio=None, segments=[], usage=meter.snapshot())
            _write_run_log(log_dir, question, steps, registry, answer, True, used_ms,
                           mode="strict", grounded_ratio=None, numeric_warnings=0,
                           usage=meter.snapshot())
            return
        yield final(
            answer, sources, att.grounded, step, used_ms, agent_id,
            mode=answer_mode,
            grounded_ratio=att.grounded_ratio,
            segments=_segments_payload(att),
            usage=meter.snapshot(),
        )
        _write_run_log(
            log_dir, question, steps, registry, answer, att.grounded, used_ms,
            mode=answer_mode, grounded_ratio=att.grounded_ratio,
            numeric_warnings=att.numeric_warnings,
            usage=meter.snapshot(),
        )
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
    mode: str = "",
    grounded_ratio: Optional[float] = None,
    numeric_warnings: int = 0,
    usage: Optional[dict] = None,
    intent: str = "",
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
        "mode": mode,
        "grounded_ratio": grounded_ratio,
        "numeric_warnings": numeric_warnings,
        "usage": usage,
    }
    if intent:
        record["intent"] = intent
    if error:
        record["error"] = error
    try:
        import os

        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, LOG_FILE), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning("写 Agent 运行日志失败：%s", e)
