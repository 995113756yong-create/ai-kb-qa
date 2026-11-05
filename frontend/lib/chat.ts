import type { SearchHit, Segment, Source, ToolCallArgs } from "@/lib/types";

// 页面状态里用的消息与步骤模型。和 lib/types.ts 的后端类型分开：
// 前者是渲染用的视图模型，后者是接口契约。

export type Step =
  | { kind: "thought"; key: string; text: string }
  | { kind: "decompose"; key: string; queries: string[] }
  | { kind: "tool_call"; key: string; name: string; args: ToolCallArgs }
  | { kind: "tool_result"; key: string; name: string; ok: boolean; summary: string; hits?: SearchHit[] };

export type Phase = "understand" | "research" | "read" | "answer" | "verify" | "done";

const PHASE_ORDER: Phase[] = ["understand", "research", "read", "answer", "verify", "done"];

/** 阶段推进只进不退：取更靠后的阶段。 */
export function advancePhase(current: Phase, next: Phase): Phase {
  return PHASE_ORDER.indexOf(next) > PHASE_ORDER.indexOf(current) ? next : current;
}

export type Feedback = "up" | "down" | null;

export type ChatMessage =
  | { id: string; role: "user"; text: string; createdAt: number }
  | {
      id: string;
      role: "assistant";
      mode: "agent" | "fast";
      steps: Step[];
      answer: string;
      sources: Source[] | null;
      segments: Segment[] | null;
      groundedRatio: number | null;
      answerMode: string | null;
      running: boolean;
      stopped: boolean;
      error: string | null;
      elapsedMs: number | null;
      createdAt: number;
      /** 当前推理阶段，运行中有值 */
      phase: Phase;
      /** 该问题对应会话，用于重新生成 */
      question: string;
      feedback: Feedback;
    };

export type Conversation = {
  id: string;
  agentId: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
};

export const FEEDBACK_REASONS = ["答非所问", "事实错误", "引用不准", "其他"] as const;
