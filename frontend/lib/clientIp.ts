// 可信代理追加的 X-Forwarded-For 解析。
//
// X-Forwarded-For 的格式是「客户端, 代理1, 代理2, ...」，越靠左越不可信：
// 最左侧那项完全由客户端自己决定（curl -H 想写什么都行）。
// 只有右侧由我们自己的代理追加的几项才可信，因此这里从右往左取第 hops 个。

/** Next.js 前面会追加 XFF 的可信代理层数，默认 1（Sealos Ingress 一层）。 */
export function trustedHops(): number {
  const n = Number(process.env.TRUSTED_PROXY_HOPS ?? "1");
  return Number.isInteger(n) && n >= 1 ? n : 1;
}

/**
 * 从 XFF 中取出真实客户端 IP。
 *
 * @param xff  原始的 X-Forwarded-For 请求头
 * @param hops 可信代理层数
 * @returns 可信的客户端 IP；XFF 缺失或层数不足时返回空串
 */
export function clientIpOf(xff: string | null, hops: number): string {
  const parts = (xff ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return parts.length >= hops ? parts[parts.length - hops] : "";
}
