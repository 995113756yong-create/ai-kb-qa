"use client";

import { useRef } from "react";

type Props = {
  disabled: boolean;
  running: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
};

export default function ChatInput({ disabled, running, onSend, onStop }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  function submit() {
    const value = ref.current?.value.trim() ?? "";
    if (!value || disabled || running) {
      return;
    }
    onSend(value);
    if (ref.current) {
      ref.current.value = "";
    }
  }

  return (
    <div className="flex items-end gap-2 border-t border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
      <textarea
        ref={ref}
        rows={2}
        disabled={disabled}
        placeholder={disabled ? "请先上传文档" : "提问…（Enter 发送，Shift+Enter 换行）"}
        aria-label="提问输入框"
        data-testid="chat-input"
        onKeyDown={(event) => {
          // 输入法组字时的 Enter 是候选词确认，不能当成发送
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            submit();
          }
        }}
        className="max-h-40 flex-1 resize-y rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-zinc-100 disabled:text-zinc-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
      />
      <button
        type="button"
        onClick={running ? onStop : submit}
        data-testid="send-button"
        className={`h-10 rounded-md px-4 text-sm font-medium text-white transition-colors ${
          running ? "bg-zinc-500 hover:bg-zinc-600" : "bg-blue-600 hover:bg-blue-700"
        } disabled:opacity-50`}
        disabled={!running && disabled}
      >
        {running ? "停止" : "发送"}
      </button>
    </div>
  );
}
