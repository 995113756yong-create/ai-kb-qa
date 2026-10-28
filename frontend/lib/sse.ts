import type { AgentEvent } from "@/lib/types";

// SSE 解析器：后端可能把一个事件拆到多个数据块，也可能一个数据块里塞多个事件。
// 这里只负责按 \n\n 切分事件、按行解析字段，不做业务判断。

export type SSEHandler = (event: AgentEvent) => void;

export type SSEParser = {
  push: (chunk: string) => void;
  flush: () => void;
};

type ParsedEvent = { event: string; data: string };

function parseBlock(block: string): ParsedEvent | null {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const rawLine of block.split("\n")) {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    // 以冒号开头的是注释行，心跳就是这种
    if (!line || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }
  return { event: eventName, data: dataLines.join("\n") };
}

export function createSSEParser(onEvent: SSEHandler): SSEParser {
  let buffer = "";

  function dispatch(block: string): void {
    const parsed = parseBlock(block);
    if (!parsed) {
      return;
    }
    try {
      const payload = JSON.parse(parsed.data) as AgentEvent;
      onEvent(payload);
    } catch {
      // 单个坏事件不该中断整条流，记一条告警继续解析后面的事件
      console.warn("[sse] 忽略无法解析的事件:", parsed.data.slice(0, 200));
    }
  }

  return {
    push(chunk: string): void {
      buffer += chunk;
      // 兼容 \n\n 与 \r\n\r\n 两种分隔
      const normalized = buffer.replace(/\r\n/g, "\n");
      const blocks = normalized.split("\n\n");
      // 最后一段可能是不完整的事件，留在缓冲区等下一次
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        dispatch(block);
      }
    },
    flush(): void {
      if (buffer.trim()) {
        dispatch(buffer);
      }
      buffer = "";
    },
  };
}
