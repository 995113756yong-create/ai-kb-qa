import type { Segment, Source, ToolCallArgs } from "@/lib/types";

// 页面状态里用的消息与步骤模型。和 lib/types.ts 的后端类型分开：
// 前者是渲染用的视图模型，后者是接口契约。

export type Step =
  | { kind: "intent"; key: string; intent: string; reason: string }
  | { kind: "decompose"; key: string; queries: string[] }
  | { kind: "thought"; key: string; text: string }
  | { kind: "tool_call"; key: string; name: string; args: ToolCallArgs }
  | { kind: "tool_result"; key: string; name: string; ok: boolean; summary: string };

export type ChatMessage =
  | { id: string; role: "user"; text: string }
  | {
      id: string;
      role: "assistant";
      mode: "agent" | "fast";
      steps: Step[];
      answer: string;
      sources: Source[];
      grounded: boolean;
      running: boolean;
      stopped: boolean;
      error: string | null;
      elapsedMs: number | null;
      // 句子级溯源（Agent 模式且收到 final 时填充）
      segments: Segment[] | null;
      groundedRatio: number | null;
      answerMode: "strict" | "reference" | null;
    };

// 一次对话 = 一个专家 + 一组消息。切换专家清空消息，旧会话不保留：
// 知识库按专家隔离，跨专家保留消息会让引用指向另一个库的文档，反而误导。
export type Conversation = {
  agentId: string;
  messages: ChatMessage[];
};
