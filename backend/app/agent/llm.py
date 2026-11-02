"""大模型调用抽象：Agent 只依赖这里的协议，测试用脚本化的假实现替换。"""
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Protocol

from app import config


@dataclass
class ToolCall:
    """模型发起的一次工具调用，arguments 保留原始 JSON 字符串。"""

    id: str
    name: str
    arguments: str


@dataclass
class Usage:
    """一次调用的 token 用量，用于评测报告的延迟/成本统计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class AssistantTurn:
    """模型一轮输出：可能只有文本，可能只有工具调用，也可能两者都有。"""

    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Optional[Usage] = None


class AgentLLM(Protocol):
    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None) -> AssistantTurn:
        ...

    def stream(self, messages: List[dict]) -> Iterator[str]:
        ...


class OpenAICompatibleLLM:
    """基于 openai 官方 SDK 的实现，兼容硅基流动等 OpenAI 协议服务。"""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
    ):
        from openai import OpenAI

        # 运行期读配置，而不是把模块级常量当默认参数绑死；
        # 否则测试里 monkeypatch config 之后仍然会拿到导入时的旧值
        self.model = model or config.AGENT_MODEL
        self.temperature = temperature
        self._client = OpenAI(
            api_key=api_key or config.OPENAI_API_KEY,
            base_url=base_url or config.OPENAI_API_BASE,
        )

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
        usage = None
        if getattr(response, "usage", None):
            usage = Usage(
                prompt_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
            )
        return AssistantTurn(content=message.content or "", tool_calls=calls, usage=usage)

    def stream(self, messages: List[dict]):
        """流式回答。yield str 增量；结束时额外 yield 一个 Usage（拿到时）。

        LLM_STREAM_USAGE 开启时请求 stream_options.include_usage，
        模型服务会在流末尾发一个只有 usage 没有 choices 的块。
        在流结束时 yield Usage 对象而不是改签名：测试里只 yield 字符串的
        假 LLM 不受影响，MeteredLLM 负责过滤非字符串项。
        """
        kwargs = {}
        if config.LLM_STREAM_USAGE:
            kwargs["stream_options"] = {"include_usage": True}
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            stream=True,
            **kwargs,
        )
        usage = None
        for chunk in stream:
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage = Usage(
                    prompt_tokens=getattr(chunk_usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(chunk_usage, "completion_tokens", 0) or 0,
                )
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
        if usage is not None:
            yield usage
