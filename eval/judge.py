"""LLM-as-judge：忠实度评判。

对每条 kind=kb 的句子，把这句话和它引用的片段全文交给评判模型：
这句话能否被证据直接支持。不允许借助常识补全；数字、范围、条件必须一致。

单题忠实度 = 被支持的 kb 句数 / kb 句总数；整体指标按句数加权平均。
建议评判模型与生成模型不同（JUDGE_MODEL），减少自我偏好。
"""
import json
import re

JUDGE_PROMPT = """你是严格的事实核查员。判断【陈述】是否能被【证据】直接支持。
不允许借助常识补全；数字、范围、条件必须一致。
只输出 JSON：{"supported": true/false, "reason": "一句话"}
【证据】{evidence}
【陈述】{statement}"""

_RETRY = 1  # JSON 解析失败时重试一次


class JudgeClient:
    """openai SDK 客户端的薄包装，可注入假实现做测试。"""

    def __init__(self, model=None, api_key=None, base_url=None, mock=False):
        self.mock = mock
        self.model = model
        if mock:
            self._client = None
            return
        from openai import OpenAI

        import os

        self._client = OpenAI(
            api_key=api_key or os.getenv("JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("JUDGE_API_BASE") or os.getenv("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
        )
        self.model = model or os.getenv("JUDGE_MODEL") or os.getenv("AGENT_MODEL")

    def complete(self, evidence: str, statement: str) -> dict:
        """返回 {"supported": bool, "reason": str}；解析失败重试一次，再失败返回 None。"""
        if self.mock:
            return {"supported": True, "reason": "mock"}
        prompt = JUDGE_PROMPT.replace("{evidence}", evidence).replace("{statement}", statement)
        for _ in range(_RETRY + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                text = resp.choices[0].message.content or ""
                m = re.search(r"\{[^{}]*\}", text, re.S)
                if not m:
                    continue
                data = json.loads(m.group(0))
                if isinstance(data.get("supported"), bool):
                    return data
            except Exception:
                continue
        return None


def judge_segments(segments: list, sources: list, question: str, client: JudgeClient) -> list:
    """对每条 kb 句做忠实度评判。

    返回与 kb 句对应的 [(segment, verdict)]，verdict 为 None 表示无法评判。
    只检查当前句子引用的片段全文，与 attribution 的数字检查同一口径。
    """
    by_index = {s["index"]: s for s in sources}
    out = []
    for seg in segments:
        if seg.get("kind") != "kb":
            continue
        cits = [c for c in seg.get("citations", []) if c in by_index]
        if not cits:
            continue
        evidence = "\n".join(
            (by_index[c].get("content") or by_index[c].get("snippet") or "") for c in cits
        )
        # 陈述里去掉引用标记和列表符号，只留正文
        statement = re.sub(r"\[\d+\]", "", seg.get("text", "")).strip()
        verdict = client.complete(evidence, statement)
        out.append((seg, verdict))
    return out


def faithfulness(results: list) -> float | None:
    """整体忠实度：所有 kb 句的加权平均（None 的不计入）。"""
    supported = 0
    total = 0
    for verdicts in results:
        for _, verdict in verdicts:
            if verdict is None:
                continue
            total += 1
            if verdict.get("supported"):
                supported += 1
    if total == 0:
        return None
    return supported / total
