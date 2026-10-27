import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ChatInput from "@/components/ChatInput";

describe("ChatInput", () => {
  it("Enter 发送，Shift+Enter 换行", async () => {
    const onSend = vi.fn();
    render(<ChatInput disabled={false} running={false} onSend={onSend} onStop={() => {}} />);

    const input = screen.getByTestId("chat-input");
    await userEvent.type(input, "你好");
    await userEvent.keyboard("{Enter}");

    expect(onSend).toHaveBeenCalledWith("你好");
  });

  it("输入法组字时按 Enter 不发送", async () => {
    const onSend = vi.fn();
    render(<ChatInput disabled={false} running={false} onSend={onSend} onStop={() => {}} />);

    const input = screen.getByTestId("chat-input") as HTMLTextAreaElement;
    await userEvent.type(input, "nihao");

    // 模拟输入法组字状态（isComposing 为 true）下按 Enter
    const composing = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
      isComposing: true,
    });
    input.dispatchEvent(composing);

    expect(onSend).not.toHaveBeenCalled();
  });

  it("空内容不发送", async () => {
    const onSend = vi.fn();
    render(<ChatInput disabled={false} running={false} onSend={onSend} onStop={() => {}} />);

    await userEvent.type(screen.getByTestId("chat-input"), "   ");
    await userEvent.keyboard("{Enter}");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("生成过程中按钮变成停止并触发 onStop", async () => {
    const onStop = vi.fn();
    render(<ChatInput disabled={false} running onSend={() => {}} onStop={onStop} />);

    const button = screen.getByTestId("send-button");
    expect(button).toHaveTextContent("停止");

    await userEvent.click(button);
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("没有文档时禁用输入框", () => {
    render(<ChatInput disabled running={false} onSend={() => {}} onStop={() => {}} />);

    expect(screen.getByTestId("chat-input")).toBeDisabled();
    expect(screen.getByTestId("chat-input")).toHaveAttribute("placeholder", "请先上传文档");
  });
});
