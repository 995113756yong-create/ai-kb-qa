import { describe, expect, it } from "vitest";

import type { ChatMessage } from "@/lib/chat";
import { MAX_HISTORY_TURNS, buildHistory } from "@/lib/history";

// 从会话消息构造多轮 history。
// 只收录正常完成的一问一答：报错、停止、仍在运行的回答连同对应问题一起跳过。

function user(text: string): ChatMessage {
  return { id: `u-${text}`, role: "user", text, createdAt: 1 };
}

function assistant(answer: string, over: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: `a-${answer}`,
    role: "assistant",
    mode: "agent",
    steps: [],
    answer,
    sources: null,
    segments: null,
    groundedRatio: null,
    answerMode: null,
    elapsedMs: 1,
    phase: "done",
    question: "",
    feedback: null,
    createdAt: 1,
    ...over,
  } as ChatMessage;
}

describe("buildHistory", () => {
  it("交替的 4 轮只取最近 3 轮，且按时间正序", () => {
    const msgs: ChatMessage[] = [];
    for (let i = 1; i <= 4; i++) {
      msgs.push(user(`问题${i}`));
      msgs.push(assistant(`回答${i}`));
    }

    const h = buildHistory(msgs);
    expect(h).toHaveLength(MAX_HISTORY_TURNS * 2);
    expect(h[0]).toEqual({ role: "user", content: "问题2" });
    expect(h[1]).toEqual({ role: "assistant", content: "回答2" });
    expect(h[4]).toEqual({ role: "user", content: "问题4" });
    expect(h[5]).toEqual({ role: "assistant", content: "回答4" });
  });

  it("error / stopped / running / 空回答 连同对应问题一起跳过", () => {
    const msgs: ChatMessage[] = [
      user("q1"),
      assistant("a1"),
      user("q2"),
      assistant("", { error: "boom" }),
      user("q3"),
      assistant("a3", { stopped: true }),
      user("q4"),
      assistant("a4", { running: true }),
      user("q5"),
      assistant("   "),
      user("q6"),
      assistant("a6"),
    ];

    const h = buildHistory(msgs);
    expect(h).toEqual([
      { role: "user", content: "q1" },
      { role: "assistant", content: "a1" },
      { role: "user", content: "q6" },
      { role: "assistant", content: "a6" },
    ]);
  });

  it("beforeIndex 截断：不含该位置及之后的消息", () => {
    const msgs: ChatMessage[] = [
      user("q1"),
      assistant("a1"),
      user("q2"),
      assistant("a2"),
    ];
    // 只看到 q2 之前 -> 只有第一轮
    const h = buildHistory(msgs, 2);
    expect(h).toEqual([
      { role: "user", content: "q1" },
      { role: "assistant", content: "a1" },
    ]);
  });

  it("去掉回答里的引用编号，并截断到 600 字", () => {
    const long = "很长的回答".repeat(300);
    const msgs: ChatMessage[] = [user("q"), assistant(`${long} [1] [2]`)];

    const h = buildHistory(msgs);
    expect(h[1].content).not.toContain("[1]");
    expect(h[1].content).not.toContain("[2]");
    expect(h[1].content.length).toBeLessThanOrEqual(600);
  });

  it("用户问题截断到 1000 字", () => {
    const msgs: ChatMessage[] = [user("问".repeat(2000)), assistant("答")];
    const h = buildHistory(msgs);
    expect(h[0].content.length).toBeLessThanOrEqual(1000);
  });

  it("空会话返回空数组", () => {
    expect(buildHistory([])).toEqual([]);
  });

  it("末尾只有用户消息（未回答）时不收录", () => {
    const msgs: ChatMessage[] = [user("q1"), assistant("a1"), user("q2")];
    const h = buildHistory(msgs);
    expect(h).toEqual([
      { role: "user", content: "q1" },
      { role: "assistant", content: "a1" },
    ]);
  });
});
