"use client";

// 消息操作条：复制 / 反馈。复制成功后按钮文案短暂切换。
// 反馈接口失败静默提示（toast 由父组件决定）。

import { useState } from "react";

import { toast } from "sonner";

import { sendFeedback } from "@/lib/api";
import { cn } from "@/lib/utils";

export type MessageActionsProps = {
  answer: string;
  question: string;
  agentId?: string;
  mode?: string | null;
  groundedRatio?: number | null;
  className?: string;
};

export function MessageActions({ answer, question, agentId, mode, groundedRatio, className }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);
  const [rating, setRating] = useState<"up" | "down" | null>(null);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("复制失败");
    }
  };

  const onFeedback = async (next: "up" | "down") => {
    // 重复点击同一评分视为取消；切换评分则覆盖
    const final = rating === next ? null : next;
    try {
      await sendFeedback({
        agent_id: agentId,
        question,
        answer,
        rating: final ?? next,
        mode: mode ?? null,
        grounded_ratio: groundedRatio ?? null,
      });
      setRating(final);
      if (final) toast.success(final === "up" ? "已记录：有帮助" : "已记录：没帮助");
    } catch {
      toast.error("反馈提交失败");
    }
  };

  return (
    <div className={cn("mt-2 flex items-center gap-1 text-xs text-muted-foreground", className)}>
      <button
        type="button"
        data-testid="copy-answer"
        onClick={() => void onCopy()}
        className="rounded-md px-2 py-1 transition-colors hover:bg-muted hover:text-foreground"
      >
        {copied ? "已复制" : "复制"}
      </button>
      <span className="text-border">|</span>
      <button
        type="button"
        data-testid="feedback-up"
        onClick={() => void onFeedback("up")}
        className={cn("rounded-md px-2 py-1 transition-colors hover:bg-muted hover:text-foreground", rating === "up" && "text-primary")}
      >
        👍 有帮助
      </button>
      <button
        type="button"
        data-testid="feedback-down"
        onClick={() => void onFeedback("down")}
        className={cn("rounded-md px-2 py-1 transition-colors hover:bg-muted hover:text-foreground", rating === "down" && "text-primary")}
      >
        👎 没帮助
      </button>
    </div>
  );
}
