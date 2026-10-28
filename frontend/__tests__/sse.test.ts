import { describe, expect, it, vi } from "vitest";

import { createSSEParser } from "@/lib/sse";
import type { AgentEvent } from "@/lib/types";

function collect() {
  const events: AgentEvent[] = [];
  const parser = createSSEParser((event) => events.push(event));
  return { events, parser };
}

describe("sse parser", () => {
  it("把拆在多个数据块里的同一个事件拼起来", () => {
    const { events, parser } = collect();
    const full = 'event: thought\ndata: {"type":"thought","step":1,"text":"思考中"}\n\n';

    parser.push(full.slice(0, 12));
    expect(events).toHaveLength(0);

    parser.push(full.slice(12, 30));
    expect(events).toHaveLength(0);

    parser.push(full.slice(30));
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: "thought", step: 1, text: "思考中" });
  });

  it("一个数据块里包含多个事件", () => {
    const { events, parser } = collect();
    parser.push(
      'event: step\ndata: {"type":"step","step":1}\n\n' +
        'event: answer_delta\ndata: {"type":"answer_delta","text":"你好"}\n\n',
    );

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: "step", step: 1 });
    expect(events[1]).toEqual({ type: "answer_delta", text: "你好" });
  });

  it("支持 CRLF 换行", () => {
    const { events, parser } = collect();
    parser.push('event: step\r\ndata: {"type":"step","step":2}\r\n\r\n');

    expect(events).toEqual([{ type: "step", step: 2 }]);
  });

  it("忽略心跳注释行", () => {
    const { events, parser } = collect();
    parser.push(": ping\n\n");
    parser.push('event: step\ndata: {"type":"step","step":1}\n\n');

    expect(events).toEqual([{ type: "step", step: 1 }]);
  });

  it("跳过非法 JSON 并告警", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { events, parser } = collect();

    parser.push("event: step\ndata: {不是 JSON}\n\n");
    expect(events).toHaveLength(0);
    expect(warn).toHaveBeenCalled();

    parser.push('event: step\ndata: {"type":"step","step":3}\n\n');
    expect(events).toEqual([{ type: "step", step: 3 }]);
    warn.mockRestore();
  });

  it("flush 会处理末尾没有空行的残留事件", () => {
    const { events, parser } = collect();
    parser.push('event: step\ndata: {"type":"step","step":4}');
    expect(events).toHaveLength(0);

    parser.flush();
    expect(events).toEqual([{ type: "step", step: 4 }]);
  });
});
