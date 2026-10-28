"use client";

import AgentTrace from "@/components/AgentTrace";
import AnswerView from "@/components/AnswerView";
import SourceCards from "@/components/SourceCards";
import type { ChatMessage } from "@/lib/chat";

type Props = {
  messages: ChatMessage[];
  onJumpToSource: (messageId: string, index: number) => void;
};

export default function MessageList({ messages, onJumpToSource }: Props) {
  return (
    <div className="flex flex-col gap-4">
      {messages.map((message) => {
        if (message.role === "user") {
          return (
            <div key={message.id} className="flex justify-end">
              <p className="max-w-[85%] whitespace-pre-wrap rounded-lg bg-blue-600 px-3 py-2 text-sm text-white">
                {message.text}
              </p>
            </div>
          );
        }

        return (
          <article
            key={message.id}
            id={message.id}
            data-testid={`assistant-${message.id}`}
            className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
          >
            {message.mode === "agent" && (
              <AgentTrace
                steps={message.steps}
                running={message.running}
                elapsedMs={message.elapsedMs}
                defaultOpen={false}
              />
            )}

            {!message.grounded && message.answer && (
              <p
                role="status"
                data-testid="ungrounded-warning"
                className="mb-2 rounded-md bg-yellow-50 px-2 py-1.5 text-xs text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-200"
              >
                该回答未引用文档内容，请谨慎参考
              </p>
            )}

            {message.stopped && (
              <p
                role="status"
                data-testid="stopped-hint"
                className="mb-2 rounded-md bg-zinc-100 px-2 py-1.5 text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
              >
                已停止生成
              </p>
            )}

            {message.error && (
              <p role="alert" className="rounded-md bg-red-50 px-2 py-1.5 text-xs text-red-600">
                {message.error}
              </p>
            )}

            {message.answer ? (
              <AnswerView
                text={message.answer}
                onJump={(index) => onJumpToSource(message.id, index)}
              />
            ) : (
              !message.error && !message.stopped && (
                <p className="text-xs text-zinc-400">思考中…</p>
              )
            )}

            <SourceCards sources={message.sources} />
          </article>
        );
      })}
    </div>
  );
}
