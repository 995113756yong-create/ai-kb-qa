import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import MessageList from "@/components/MessageList";

// 空状态：显示专家名、文档数、推荐问题；点推荐问题直接发送。

describe("MessageList 空状态（M6.4）", () => {
  it("有推荐问题时渲染卡片并可点击", async () => {
    const onPick = vi.fn();
    render(
      <MessageList
        messages={[]}
        onJumpToSource={() => {}}
        starters={["产品 A 的月费是多少？", "支持哪些支付方式？"]}
        onPickStarter={onPick}
        agentName="通用助手"
        docCount={3}
      />,
    );

    expect(screen.getByTestId("starter-questions")).toBeInTheDocument();
    expect(screen.getByText("产品 A 的月费是多少？")).toBeInTheDocument();

    await userEvent.click(screen.getByText("产品 A 的月费是多少？"));
    expect(onPick).toHaveBeenCalledWith("产品 A 的月费是多少？");
  });

  it("最多显示 4 条推荐问题", () => {
    render(
      <MessageList
        messages={[]}
        onJumpToSource={() => {}}
        starters={["q1", "q2", "q3", "q4", "q5", "q6"]}
        onPickStarter={() => {}}
      />,
    );
    expect(screen.getByText("q4")).toBeInTheDocument();
    expect(screen.queryByText("q5")).not.toBeInTheDocument();
  });

  it("没有推荐问题时只显示引导文案", () => {
    render(<MessageList messages={[]} onJumpToSource={() => {}} agentName="通用助手" docCount={0} />);
    expect(screen.queryByTestId("starter-questions")).not.toBeInTheDocument();
    expect(screen.getByText(/先上传文档/)).toBeInTheDocument();
  });

  it("有文档时显示文档数", () => {
    render(<MessageList messages={[]} onJumpToSource={() => {}} docCount={5} />);
    expect(screen.getByText(/已索引 5 份文档/)).toBeInTheDocument();
  });

  it("显示专家名", () => {
    render(<MessageList messages={[]} onJumpToSource={() => {}} agentName="健身教练" />);
    expect(screen.getByText(/向「健身教练」提问/)).toBeInTheDocument();
  });

  it("starters 为空数组时不渲染区块", () => {
    render(
      <MessageList messages={[]} onJumpToSource={() => {}} starters={[]} onPickStarter={() => {}} />,
    );
    expect(screen.queryByTestId("starter-questions")).not.toBeInTheDocument();
  });
});
