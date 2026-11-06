// 数字与时间格式化工具：体积、耗时、相对时间。
// 体积用二进制单位（KiB/MiB），耗时展示带单位，相对时间中文口语化。

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 KB";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(kb < 10 ? 1 : 0)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(mb < 10 ? 1 : 0)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

export function formatMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "-";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rest = Math.round(s % 60);
  return `${m}m${rest}s`;
}

type Tr = (key: string, vars?: Record<string, string | number>) => string;

/**
 * 相对时间：刚刚 / N 分钟前 / N 小时前 / N 天前，超过 30 天显示日期。
 *
 * 第 2 个参数可以是 now 时间戳，也可以传翻译函数（国际化用）。
 * 这样保持旧的 timeAgo(ts) / timeAgo(ts, now) 调用不变，
 * 需要多语言时传 t 即可。
 */
export function timeAgo(
  ts: number,
  nowOrT: number | Tr = Date.now(),
): string {
  const now = typeof nowOrT === "number" ? nowOrT : Date.now();
  const tr =
    typeof nowOrT === "function"
      ? nowOrT
      : ((key: string, vars?: Record<string, string | number>) => {
          // 无翻译函数时的中文兜底，与旧行为一致
          const n = vars?.n ?? 0;
          switch (key) {
            case "common.justNow":
              return "刚刚";
            case "common.minutesAgo":
              return `${n} 分钟前`;
            case "common.hoursAgo":
              return `${n} 小时前`;
            case "common.daysAgo":
              return `${n} 天前`;
            default:
              return key;
          }
        }) as Tr;

  const diff = now - ts;
  if (diff < 60_000) return tr("common.justNow");
  if (diff < 3_600_000) return tr("common.minutesAgo", { n: Math.floor(diff / 60_000) });
  if (diff < 86_400_000) return tr("common.hoursAgo", { n: Math.floor(diff / 3_600_000) });
  if (diff < 30 * 86_400_000) return tr("common.daysAgo", { n: Math.floor(diff / 86_400_000) });
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
