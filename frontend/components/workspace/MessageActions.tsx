"use client";

// 消息操作条：复制 / 反馈。复制成功后按钮文案短暂切换。
// 反馈接口失败静默提示（toast 由父组件决定）。

import { useState } from "react";

import { toast } from "sonner";

import { sendFeedback } from "@/lib/api";
import type { Source } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export type MessageActionsProps = {
  answer: string;
  question: string;
  agentId?: string;
  mode?: string | null;
  groundedRatio?: number | null;
  /** 证据列表：用于「复制（带出处）」 */
  sources?: Source[] | null;
  className?: string;
};

export function MessageActions({
  answer,
  question,
  agentId,
  mode,
  groundedRatio,
  sources,
  className,
}: MessageActionsProps) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const [copiedWithSources, setCopiedWithSources] = useState(false);
  const [rating, setRating] = useState<"up" | "down" | null>(null);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error(t("chat.copyFailed"));
    }
  };

  // 复制正文（去掉 [n]），末尾附出处清单
  const onCopyWithSources = async () => {
    // 去掉 [n] 后可能留下多余空格（"30 元 [1]。" -> "30 元 。"），顺带清理
    const body = answer
      .replace(/\[\d+\]/g, "")
      .replace(/[ \t]+([。！？!?；;，,])/g, "$1")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
    const lines = (sources ?? []).map(
      (s) =>
        `[${s.index}] ${s.source ?? t("common.unknownDoc")}${s.page !== null && s.page !== undefined ? ` ${t("common.page", { n: s.page })}` : ""}`,
    );
    const text = lines.length ? `${body}\n\n${t("chat.sources")}：\n${lines.join("\n")}` : body;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedWithSources(true);
      window.setTimeout(() => setCopiedWithSources(false), 1500);
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
      if (final) toast.success(final === "up" ? t("chat.feedbackUp") : t("chat.feedbackDown"));
    } catch {
      toast.error(t("chat.feedbackFailed"));
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
        {copied ? t("common.copied") : t("common.copy")}
      </button>
      <span className="text-border">|</span>
      <button
        type="button"
        data-testid="copy-with-sources"
        onClick={() => void onCopyWithSources()}
        className="rounded-md px-2 py-1 transition-colors hover:bg-muted hover:text-foreground"
      >
        {copiedWithSources ? t("common.copied") : t("chat.copyWithSources")}
      </button>
      <span className="text-border">|</span>
      <button
        type="button"
        data-testid="feedback-up"
        onClick={() => void onFeedback("up")}
        className={cn("rounded-md px-2 py-1 transition-colors hover:bg-muted hover:text-foreground", rating === "up" && "text-primary")}
      >
        👍 {t("chat.feedbackUp")}
      </button>
      <button
        type="button"
        data-testid="feedback-down"
        onClick={() => void onFeedback("down")}
        className={cn("rounded-md px-2 py-1 transition-colors hover:bg-muted hover:text-foreground", rating === "down" && "text-primary")}
      >
        👎 {t("chat.feedbackDown")}
      </button>
    </div>
  );
}
