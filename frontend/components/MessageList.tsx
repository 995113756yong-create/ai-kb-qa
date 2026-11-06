"use client";

import AgentTrace from "@/components/AgentTrace";
import AnswerView from "@/components/AnswerView";
import SourceCards from "@/components/SourceCards";
import type { ChatMessage } from "@/lib/chat";

type Props = {
  messages: ChatMessage[];
  onJumpToSource: (messageId: string, index: number) => void;
};

function ratioColor(ratio: number): string {
  if (ratio >= 0.8) {
    return "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-200";
  }
  if (ratio >= 0.4) {
    return "bg-general-bg text-general";
  }
  return "bg-muted text-muted-foreground";
}

function TrustBadge({ message }: { message: ChatMessage & { role: "assistant" } }) {
  const hasSegments = (message.segments?.length ?? 0) > 0;
  if (!hasSegments) {
    return null;
  }
  const kb = message.segments?.filter((s) => s.kind === "kb").length ?? 0;
  const total =
    (message.segments?.filter((s) => s.kind === "kb").length ?? 0) +
    (message.segments?.filter((s) => s.kind === "general").length ?? 0);
  const warnCount = message.segments?.reduce((acc, s) => acc + s.warnings.length, 0) ?? 0;
  const ratio = message.groundedRatio;

  return (
    <div className="mb-2 flex flex-wrap items-center gap-1.5 text-[11px]" data-testid="trust-badge">
      <span
        className={`rounded-full px-2 py-0.5 ${
          message.answerMode === "strict"
            ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-200"
            : "bg-sky-50 text-sky-700 dark:bg-sky-900/30 dark:text-sky-200"
        }`}
      >
        {message.answerMode === "strict" ? "严格模式" : "参考模式"}
      </span>
      {ratio !== null && ratio !== undefined && (
        <span className={`rounded-full px-2 py-0.5 ${ratioColor(ratio)}`} data-testid="kb-ratio">
          知识库依据 {Math.round(ratio * 100)}%（{kb}/{total} 句）
        </span>
      )}
      {warnCount > 0 && (
        <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-destructive" data-testid="numeric-warning">
          ⚠ {warnCount} 处数字未在出处中找到
        </span>
      )}
      <span className="text-muted-foreground">
        琥珀底=一般知识，红波浪=数字存疑
      </span>
    </div>
  );
}

export default function MessageList({ messages, onJumpToSource }: Props) {
  if (messages.length === 0) {
    // 空状态撑满消息区，保证输入框稳定贴在底部
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
        <div className="text-3xl">💬</div>
        <p className="text-sm font-medium">开始一次对话</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          选择一个专家，然后提问。回答会标注知识库依据与数字溯源性。
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      {messages.map((message) => {
        if (message.role === "user") {
          return (
            <div key={message.id} className="message-enter flex justify-end">
              <p className="brand-gradient max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md px-3.5 py-2 text-sm text-white shadow-sm">
                {message.text}
              </p>
            </div>
          );
        }

        const isThinking = message.running && !message.answer && !message.error && !message.stopped;
        const hasSegments = (message.segments?.length ?? 0) > 0;

        return (
          <article
            key={message.id}
            id={message.id}
            data-testid={`assistant-${message.id}`}
            className="message-enter rounded-2xl rounded-tl-md border border-border bg-card p-3.5 shadow-sm"
          >
            {message.mode === "agent" && (
              <AgentTrace
                steps={message.steps}
                running={message.running}
                elapsedMs={message.elapsedMs}
                defaultOpen={false}
              />
            )}

            {hasSegments ? (
              <TrustBadge message={message} />
            ) : (
              message.groundedRatio === 0 &&
              message.answer && (
                <p
                  role="status"
                  data-testid="ungrounded-warning"
                  className="mb-2 flex items-center gap-1.5 rounded-lg bg-general-bg px-2.5 py-1.5 text-xs text-general"
                >
                  <span aria-hidden>⚠️</span>
                  该回答未引用文档内容，请谨慎参考
                </p>
              )
            )}

            {message.stopped && (
              <p
                role="status"
                data-testid="stopped-hint"
                className="mb-2 rounded-lg bg-muted px-2.5 py-1.5 text-xs text-muted-foreground"
              >
                已停止生成
              </p>
            )}

            {message.error && (
              <p role="alert" className="flex items-center gap-1.5 rounded-lg bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive">
                <span aria-hidden>⚠️</span>
                {message.error}
              </p>
            )}

            {message.answer ? (
              <AnswerView
                text={message.answer}
                segments={message.segments}
                onJump={(index) => onJumpToSource(message.id, index)}
              />
            ) : (
              !message.error &&
              !message.stopped &&
              isThinking && (
                <div className="flex items-center gap-1 py-1 text-xs text-muted-foreground">
                  <span>思考中</span>
                  <span className="flex gap-0.5">
                    <span className="thinking-dot h-1 w-1 rounded-full bg-muted-foreground" style={{ animationDelay: "0ms" }} />
                    <span className="thinking-dot h-1 w-1 rounded-full bg-muted-foreground" style={{ animationDelay: "150ms" }} />
                    <span className="thinking-dot h-1 w-1 rounded-full bg-muted-foreground" style={{ animationDelay: "300ms" }} />
                  </span>
                </div>
              )
            )}

            {!!message.sources?.length && <SourceCards sources={message.sources} />}
          </article>
        );
      })}
      </div>
    </div>
  );
}
