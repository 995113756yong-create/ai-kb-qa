import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DELETE, GET, POST } from "@/app/api/[...path]/route";

function makeRequest(path: string, init?: { method?: string; headers?: Record<string, string>; body?: string; search?: string }) {
  const url = `http://localhost:3000/api/${path}${init?.search ?? ""}`;
  return new NextRequest(url, {
    method: init?.method ?? "GET",
    headers: init?.headers,
    body: init?.body,
  });
}

function makeContext(path: string[]): { params: Promise<{ path: string[] }> } {
  return { params: Promise.resolve({ path }) };
}

const originalFetch = globalThis.fetch;

beforeEach(() => {
  delete process.env.BACKEND_URL;
});

afterEach(() => {
  vi.unstubAllGlobals();
  globalThis.fetch = originalFetch;
});

function stubUpstream(response: Response) {
  const spy = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("转发层", () => {
  it("把路径和查询串拼到后端地址上", async () => {
    process.env.BACKEND_URL = "http://api:8000";
    const spy = stubUpstream(new Response("ok", { status: 200 }));

    await GET(makeRequest("docs/abc", { search: "?x=1&y=2" }), makeContext(["docs", "abc"]));

    const [target] = spy.mock.calls[0] as [string];
    expect(target).toBe("http://api:8000/api/docs/abc?x=1&y=2");
  });

  it("没有配置 BACKEND_URL 时默认指向 localhost:8000", async () => {
    const spy = stubUpstream(new Response("ok", { status: 200 }));

    await GET(makeRequest("health"), makeContext(["health"]));

    const [target] = spy.mock.calls[0] as [string];
    expect(target).toBe("http://localhost:8000/api/health");
  });

  it("请求头只透传白名单里的几项", async () => {
    const spy = stubUpstream(new Response("ok", { status: 200 }));

    await POST(
      makeRequest("ask", {
        method: "POST",
        body: "{}",
        headers: {
          "content-type": "application/json",
          accept: "application/json",
          "accept-language": "zh-CN",
          cookie: "session=secret",
          authorization: "Bearer secret",
        },
      }),
      makeContext(["ask"]),
    );

    const [, init] = spy.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Headers;
    expect(headers.get("content-type")).toBe("application/json");
    expect(headers.get("accept")).toBe("application/json");
    expect(headers.get("accept-language")).toBe("zh-CN");
    expect(headers.get("cookie")).toBeNull();
    expect(headers.get("authorization")).toBeNull();
  });

  it("路径含 .. 时返回 400 且不请求后端", async () => {
    const spy = stubUpstream(new Response("ok"));

    const res = await GET(makeRequest("x"), makeContext(["..", "secret"]));

    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ detail: "非法路径" });
    expect(spy).not.toHaveBeenCalled();
  });

  it("路径含反斜杠或空片段时返回 400", async () => {
    stubUpstream(new Response("ok"));

    expect((await GET(makeRequest("x"), makeContext(["a\\b"]))).status).toBe(400);
    expect((await GET(makeRequest("x"), makeContext([""]))).status).toBe(400);
  });

  it("后端连不上时返回 502", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));

    const res = await GET(makeRequest("health"), makeContext(["health"]));

    expect(res.status).toBe(502);
    expect(await res.json()).toEqual({ detail: "后端服务不可用" });
  });

  it("响应头里的 content-encoding 等被去掉", async () => {
    stubUpstream(
      new Response("ok", {
        status: 200,
        headers: {
          "content-type": "text/event-stream",
          "content-encoding": "gzip",
          "content-length": "123",
          "transfer-encoding": "chunked",
          connection: "keep-alive",
          "cache-control": "no-cache",
        },
      }),
    );

    const res = await GET(makeRequest("agent/stream"), makeContext(["agent", "stream"]));

    expect(res.headers.get("content-type")).toBe("text/event-stream");
    expect(res.headers.get("cache-control")).toBe("no-cache");
    expect(res.headers.get("content-encoding")).toBeNull();
    expect(res.headers.get("content-length")).toBeNull();
    expect(res.headers.get("transfer-encoding")).toBeNull();
    expect(res.headers.get("connection")).toBeNull();
  });

  it("GET 不发送请求体，POST 以流的形式透传", async () => {
    const spy = stubUpstream(new Response("ok"));

    await GET(makeRequest("docs"), makeContext(["docs"]));
    const [, getInit] = spy.mock.calls[0] as [string, RequestInit];
    expect(getInit.body).toBeUndefined();

    await POST(
      makeRequest("ask", { method: "POST", body: '{"question":"hi"}', headers: { "content-type": "application/json" } }),
      makeContext(["ask"]),
    );
    const [, postInit] = spy.mock.calls[1] as [string, RequestInit];
    expect(postInit.body).toBeInstanceOf(ReadableStream);
  });

  it("DELETE 也被导出并转发", async () => {
    const spy = stubUpstream(new Response("ok", { status: 200 }));

    await DELETE(makeRequest("docs/abc", { method: "DELETE" }), makeContext(["docs", "abc"]));

    const [target, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(target).toBe("http://localhost:8000/api/docs/abc");
    expect(init.method).toBe("DELETE");
  });
});
