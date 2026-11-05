"use client";

// 引用编号徽章：点击滚到出处面板并切换到对应 source。
// 编号越界（后端异常数据）时降级为不可点击的纯文本。

import { cn } from "@/lib/utils";

export type CitationChipProps = {
  index: number;
  onClick?: (index: number) => void;
  className?: string;
};

export function CitationChip({ index, onClick, className }: CitationChipProps) {
  const valid = index >= 1;
  return (
    <button
      type="button"
      data-testid={`citation-${index}`}
      disabled={!valid}
      onClick={() => valid && onClick?.(index)}
      className={cn(
        "inline-flex h-5 min-w-5 items-center justify-center rounded-md border border-primary/30 bg-primary/10 px-1 align-middle text-[10px] font-semibold tabular-nums text-primary transition-colors",
        valid && "cursor-pointer hover:bg-primary/20 hover:border-primary/50",
        !valid && "opacity-50",
        className,
      )}
    >
      {index}
    </button>
  );
}
