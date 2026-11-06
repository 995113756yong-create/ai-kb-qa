import type { ChatMessage } from "@/lib/chat";
import type { HistoryTurn } from "@/lib/types";

// 从会话消息里构造多轮 history。
// 只收录正常完成的一问一答：报错、停止、仍在运行的回答连同它对应的问题一起跳过，
// 避免把失败的回答当成上下文喂给改写模型。

export const MAX_HISTORY_TURNS = 3;
const ANSWER_CHARS = 600;

const stripCitations = (s: string) => s.replace(/\[\d+\]/g, "").replace(/\s+\n/g, "\n").trim();

/**
 * 取 beforeIndex 之前最近 MAX_HISTORY_TURNS 轮“一问一答”，按时间正序返回。
 */
export function buildHistory(
  messages: ChatMessage[],
  beforeIndex = messages.length,
): HistoryTurn[] {
  const turns: HistoryTurn[][] = [];
  for (let i = 0; i < beforeIndex; i++) {
    const m = messages[i];
    const next = messages[i + 1];
    if (m.role !== "user" || !next || next.role !== "assistant" || i + 1 >= beforeIndex) continue;
    if (next.running || next.error || next.stopped || !next.answer.trim()) continue;
    turns.push([
      { role: "user", content: m.text.slice(0, 1000) },
      { role: "assistant", content: stripCitations(next.answer).slice(0, ANSWER_CHARS) },
    ]);
  }
  return turns.slice(-MAX_HISTORY_TURNS).flat();
}
