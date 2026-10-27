"""大模型调用抽象：Agent 只依赖这里的协议，测试用脚本化的假实现替换。"""
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Protocol

from app.config import AGENT_MODEL, OPENAI_API_BASE, OPENAI_API_KEY


@dataclass
class ToolCall:
    """模型发起的一次工具调用，arguments 保留原始 JSON 字符串。"""

    id: str
    name: str
    arguments: str


@dataclass
class AssistantTurn:
    """模型一轮输出：可能只有文本，可能只有工具调用，也可能两者都有。"""

    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)


class AgentLLM(Protocol):
    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None) -> AssistantTurn:
        ...

    def stream(self, messages: List[dict]) -> Iterator[str]:
        ...


class OpenAICompatibleLLM:
    """基于 openai 官方 SDK 的实现，兼容硅基流动等 OpenAI 协议服务。"""

    def __init__(
        self,
        model: str = AGENT_MODEL,
        api_key: Optional[str] = OPENAI_API_KEY,
        base_url: str = OPENAI_API_BASE,
        temperature: float = 0.1,
    ):
        from openai import OpenAI

        self.model = model
        self.temperature = temperature
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None) -> AssistantTurn:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        calls = [
            ToolCall(
                id=c.id,
                name=c.function.name,
                arguments=c.function.arguments or "{}",
            )
            for c in (message.tool_calls or [])
        ]
        return AssistantTurn(content=message.content or "", tool_calls=calls)

    def stream(self, messages: List[dict]) -> Iterator[str]:
        # 最终回答阶段不带工具，只把文本增量吐出来
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
