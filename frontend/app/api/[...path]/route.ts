import type { NextRequest } from "next/server";

import { clientIpOf, trustedHops } from "@/lib/clientIp";

// 转发层：浏览器只访问 Next.js，所有 /api/* 请求在这里转给 FastAPI。
// 必须跑在 Node runtime，才能用 fetch 流式转发请求体和响应体。
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ path: string[] }> };

// 只透传这几项请求头，其余（cookie、host、authorization 等）不下传。
// x-admin-token：写接口鉴权口令；x-forwarded-for：问答限流的客户端 IP。
const PASS_REQ = ["content-type", "accept", "accept-language", "x-admin-token"];

// 这些响应头描述的是后端那一跳的传输方式，透传会破坏本跳的流式传输
const DROP_RES = ["content-encoding", "content-length", "transfer-encoding", "connection"];

const DEFAULT_BACKEND = "http://localhost:8000";

function isIllegalSegment(segment: string): boolean {
  return !segment || segment === ".." || segment.includes("\\");
}

async function proxy(req: NextRequest, ctx: Ctx): Promise<Response> {
  const { path } = await ctx.params;

  if (path.some(isIllegalSegment)) {
    return Response.json({ detail: "非法路径" }, { status: 400 });
  }

  // 运行时读取，部署时靠环境变量切换后端地址，不能构建期写死
  const base = process.env.BACKEND_URL ?? DEFAULT_BACKEND;
  const target = `${base.replace(/\/$/, "")}/api/${path
    .map(encodeURIComponent)
    .join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  for (const name of PASS_REQ) {
    const value = req.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }

  // 透传客户端真实 IP 给后端限流。
  // 容器里所有请求的 source 都是 Next.js pod，不传 XFF 后端就只能全站共享一个限流桶。
  //
  // 只取可信代理追加的那一项，并「覆盖」而不是「追加」：
  // XFF 最左侧的值由客户端自行决定，追加会让攻击者每次换 IP 拿到新限流桶。
  const clientIp = clientIpOf(req.headers.get("x-forwarded-for"), trustedHops());
  if (clientIp) {
    headers.set("x-forwarded-for", clientIp);
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      // 浏览器断开时同步中断对后端的请求，后端才能尽早停止调用模型
      signal: req.signal,
      cache: "no-store",
      // @ts-expect-error Node 的 fetch 发送流式请求体必须显式声明 duplex
      duplex: "half",
    });

    const resHeaders = new Headers(upstream.headers);
    for (const name of DROP_RES) {
      resHeaders.delete(name);
    }

    return new Response(upstream.body, { status: upstream.status, headers: resHeaders });
  } catch {
    return Response.json({ detail: "后端服务不可用" }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST, proxy as DELETE };
