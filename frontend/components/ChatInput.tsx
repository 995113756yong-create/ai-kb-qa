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
    <div className="flex items-end gap-2 border-t border-zinc-200/80 bg-white/90 p-3 backdrop-blur-sm dark:border-zinc-800/80 dark:bg-zinc-900/90">
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
        className="max-h-40 flex-1 resize-y rounded-xl border border-zinc-200 bg-white px-3.5 py-2.5 text-sm outline-none transition-colors placeholder:text-zinc-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:bg-zinc-50 disabled:text-zinc-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:ring-indigo-900/40 dark:disabled:bg-zinc-900"
      />
      <button
        type="button"
        onClick={running ? onStop : submit}
        data-testid="send-button"
        className={`h-10 rounded-xl px-4 text-sm font-medium text-white shadow-sm transition-all active:scale-95 ${
          running ? "bg-zinc-500 hover:bg-zinc-600" : "brand-gradient hover:shadow-md"
        } disabled:opacity-50 disabled:active:scale-100`}
        disabled={!running && disabled}
      >
        {running ? "停止" : "发送"}
      </button>
    </div>
  );
}
