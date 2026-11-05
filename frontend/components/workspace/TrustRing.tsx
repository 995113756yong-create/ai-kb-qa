"use client";

// 信任环：回答的可信度指示器。评分 = 引用覆盖率（有引用句占比）。
// 纯展示组件，评分由父组件算好传入。

import { cn } from "@/lib/utils";

export type TrustRingProps = {
  /** 0-100 的信任分 */
  score: number;
  /** 悬浮提示文案，默认「引用覆盖率」 */
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
};

const SIZES = {
  sm: { box: 32, stroke: 3 },
  md: { box: 48, stroke: 4 },
  lg: { box: 72, stroke: 5 },
} as const;

function scoreColor(score: number): string {
  if (score >= 80) return "stroke-emerald-500";
  if (score >= 50) return "stroke-amber-500";
  return "stroke-rose-500";
}

export function TrustRing({ score, label, size = "md", className }: TrustRingProps) {
  const { box, stroke } = SIZES[size];
  const r = (box - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  const dash = (clamped / 100) * c;

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      data-testid="trust-ring"
      title={label ?? "引用覆盖率"}
    >
      <svg width={box} height={box} viewBox={`0 0 ${box} ${box}`} className="-rotate-90">
        <circle
          cx={box / 2}
          cy={box / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          className="stroke-muted"
        />
        <circle
          cx={box / 2}
          cy={box / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          className={cn("transition-[stroke-dasharray] duration-500", scoreColor(clamped))}
        />
      </svg>
      <span
        className={cn(
          "absolute font-semibold tabular-nums text-foreground",
          size === "sm" && "text-[10px]",
          size === "md" && "text-xs",
          size === "lg" && "text-base",
        )}
      >
        {Math.round(clamped)}
      </span>
    </div>
  );
}
