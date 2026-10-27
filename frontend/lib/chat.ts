import type { Source, ToolCallArgs } from "@/lib/types";

// 页面状态里用的消息与步骤模型。和 lib/types.ts 的后端类型分开：
// 前者是渲染用的视图模型，后者是接口契约。

export type Step =
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
      error: string | null;
      elapsedMs: number | null;
    };
