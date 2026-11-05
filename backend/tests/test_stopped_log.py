"""停止 / 断连场景的运行日志：保证每条请求结束都有记录。

原先 stream_events 直接 break，生成器不会再往下执行，这次请求不产生任何日志；
另外 7 处收尾是先 yield final 再写日志，yield 后前端若立刻断开日志同样会丢。
"""
import asyncio
import json

from app.agent.llm import AssistantTurn, ToolCall
from app.agent.runner import run_agent
from app.agent.sse import stream_events

from tests.test_runner_enhancements import ScriptedLLM, _kb


def _read_log(path):
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def test_stopped_run_writes_partial_log(tmp_path, embeddings):
    """读到第一个 answer_delta 就 close，应补写一条 stopped 记录。"""
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[AssistantTurn(content="信息足够")],
        answer_chunks=["第一段回答", "第二段回答"],
    )
    log_dir = tmp_path / "logs"

    gen = run_agent("产品A的月费是多少？", kb, llm, log_dir=str(log_dir))
    seen_delta = False
    for event in gen:
        if event.get("type") == "answer_delta" and not seen_delta:
            seen_delta = True
            gen.close()  # 模拟用户点「停止」
            break

    records = _read_log(log_dir / "agent_runs.jsonl")
    assert len(records) == 1
    rec = records[0]
    assert rec.get("stopped") is True
    # 已经生成的部分回答要留下，方便事后分析
    assert "第一段回答" in rec["answer"]
    assert rec["evidence_count"] is None


def test_normal_run_does_not_duplicate_log(tmp_path, embeddings):
    """正常跑完只写一行，且不带 stopped 字段。"""
    kb = _kb(tmp_path, embeddings)
    llm = ScriptedLLM(
        turns=[
            AssistantTurn(
                content="",
                tool_calls=[ToolCall(id="c1", name="search_kb", arguments=json.dumps({"query": "产品A"}))],
            ),
            AssistantTurn(content="够了"),
        ],
        answer_chunks=["产品A的月费是30元 [E1]"],
    )
    log_dir = tmp_path / "logs"

    list(run_agent("产品A的月费是多少？", kb, llm, log_dir=str(log_dir)))

    records = _read_log(log_dir / "agent_runs.jsonl")
    assert len(records) == 1
    assert "stopped" not in records[0]


def test_stream_events_closes_generator_on_disconnect():
    """客户端断连后必须主动 close 生成器，否则 run_agent 收不到 GeneratorExit。"""
    flag = {"closed": False}

    def gen():
        try:
            yield {"type": "answer_delta", "text": "a"}
            yield {"type": "answer_delta", "text": "b"}
            yield {"type": "final", "answer": "ab"}
        finally:
            flag["closed"] = True

    calls = {"n": 0}

    async def is_disconnected():
        # 第一次检查返回 False（让它拿到首个事件），之后返回 True
        calls["n"] += 1
        return calls["n"] > 1

    async def drain():
        agen = stream_events(gen(), is_disconnected, heartbeat_seconds=5)
        async for _ in agen:
            pass
        # 真实场景由 ASGI 层负责收尾；这里显式 aclose 等价于连接关闭后的清理
        await agen.aclose()

    asyncio.run(drain())
    assert flag["closed"] is True
