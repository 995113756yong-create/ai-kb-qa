"use client";

import AgentTrace from "@/components/AgentTrace";
import AnswerView from "@/components/AnswerView";
import { TrustSummary } from "@/components/workspace/TrustSummary";
import { CitationFocusProvider } from "@/lib/citationFocus";
import SourceCards from "@/components/SourceCards";
import type { ChatMessage } from "@/lib/chat";

type Props = {
  messages: ChatMessage[];
  onJumpToSource: (messageId: string, index: number) => void;
};

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
          <CitationFocusProvider key={message.id}>
          <article
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
              <TrustSummary message={message} />
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
                messageId={message.id}
                sources={message.sources}
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
          </CitationFocusProvider>
        );
      })}
      </div>
    </div>
  );
}
