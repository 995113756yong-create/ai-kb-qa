import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, ask, deleteAgent, deleteDoc, listDocs, streamAgent, uploadDoc } from "@/lib/api";

function mockFetch(status: number, body: unknown) {
  const spy = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

async function catchError(fn: () => Promise<unknown>): Promise<ApiError> {
  try {
    await fn();
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("期望抛出 ApiError，但没有抛");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api error 转换", () => {
  it("detail 是字符串时直接使用", async () => {
    mockFetch(400, { detail: "不支持的文件类型" });

    const error = await catchError(() => listDocs());

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(400);
    expect(error.message).toBe("不支持的文件类型");
  });

  it("detail 是数组时把各项 msg 用分号连起来", async () => {
    mockFetch(422, {
      detail: [{ msg: "字段不能为空" }, { msg: "长度超过限制" }, { loc: ["body"] }],
    });

    const error = await catchError(() => ask("x"));

    expect(error.status).toBe(422);
    expect(error.message).toBe("字段不能为空; 长度超过限制");
  });

  it("无法解析响应体时退化成 HTTP 状态码", async () => {
    mockFetch(500, null);

    const error = await catchError(() => deleteDoc("abc"));

    expect(error.status).toBe(500);
    expect(error.message).toBe("HTTP 500");
  });

  it("detail 是空数组时同样退化成状态码", async () => {
    mockFetch(503, { detail: [] });

    const error = await catchError(() => listDocs());

    expect(error.message).toBe("HTTP 503");
  });
});

describe("请求构造", () => {
  it("上传走 multipart，不手动设置 content-type", async () => {
    const spy = mockFetch(200, { status: "ok", doc_id: "d", filename: "a.txt", size: 3, chunks: 1, message: "" });
    const file = new File(["abc"], "a.txt", { type: "text/plain" });

    await uploadDoc(file);

    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/upload");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    // adminHeaders() 没存口令时返回空对象，不能是 content-type（multipart 边界由浏览器生成）
    const headers = init.headers as Record<string, string>;
    expect(headers).toBeDefined();
    expect(Object.keys(headers)).not.toContain("content-type");
    expect(Object.keys(headers)).not.toContain("Content-Type");
  });

  it("删除请求对 doc_id 做 URL 编码", async () => {
    const spy = mockFetch(200, { status: "ok", doc_id: "a b", filename: "a.txt" });

    await deleteDoc("a b");

    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/docs/a%20b");
    expect(init.method).toBe("DELETE");
  });

  it("401 时提示输入口令，保存后带 X-Admin-Token 重试一次", async () => {
    const spy = mockFetch(401, { detail: "需要管理员口令" });
    spy.mockImplementationOnce(() => Promise.resolve(new Response(JSON.stringify({ detail: "需要管理员口令" }), { status: 401 })));
    spy.mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ status: "ok", doc_id: "d", filename: "a.txt", size: 3, chunks: 1, message: "" }), { status: 200 })),
    );
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("secret-token");
    window.localStorage.clear();

    const file = new File(["abc"], "a.txt", { type: "text/plain" });
    await uploadDoc(file);

    // 第一次 401，prompt 后重试带头成功
    expect(promptSpy).toHaveBeenCalled();
    expect(spy).toHaveBeenCalledTimes(2);
    const [, retryInit] = spy.mock.calls[1] as [string, RequestInit];
    expect((retryInit.headers as Record<string, string>)["X-Admin-Token"]).toBe("secret-token");
    // 口令已存 localStorage，后续请求直接带
    expect(window.localStorage.getItem("kbqa_admin_token")).toBe("secret-token");
    promptSpy.mockRestore();
    window.localStorage.clear();
  });

  it("401 时用户取消输入则抛原错误，不重试", async () => {
    window.localStorage.clear();
    const spy = mockFetch(401, { detail: "需要管理员口令" });
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue(null);

    const file = new File(["abc"], "a.txt", { type: "text/plain" });
    await expect(uploadDoc(file)).rejects.toThrow("需要管理员口令");

    expect(promptSpy).toHaveBeenCalled();
    expect(spy).toHaveBeenCalledTimes(1);
    promptSpy.mockRestore();
  });
});

describe("agent_id 参数路由", () => {
  it("default 专家走无参数旧路径", async () => {
    const spy = mockFetch(200, { status: "ok", docs: [] });

    await listDocs("default");

    expect(spy.mock.calls[0][0]).toBe("/api/docs");
  });

  it("自定义专家带 ?agent_id=", async () => {
    const spy = mockFetch(200, { status: "ok", docs: [] });

    await listDocs("fitness-coach");

    expect(spy.mock.calls[0][0]).toBe("/api/docs?agent_id=fitness-coach");
  });

  it("uploadDoc 透传 agent_id", async () => {
    const spy = mockFetch(200, { status: "ok", doc_id: "d", filename: "a.txt", size: 3, chunks: 1, message: "" });
    const file = new File(["abc"], "a.txt", { type: "text/plain" });

    await uploadDoc(file, "cooking");

    const [url] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/upload?agent_id=cooking");
  });

  it("deleteAgent 走 /api/agents/{id}", async () => {
    const spy = mockFetch(200, { status: "ok", agent_id: "cooking", filename: "" });

    await deleteAgent("cooking");

    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/agents/cooking");
    expect(init.method).toBe("DELETE");
  });

  it("streamAgent 必须把 agent_id 放进请求体（串库 bug 回归防护）", async () => {
    // 后端 AgentRequest 只解析 body；agent_id 只放 URL 查询串会被忽略，
    // 曾导致切专家后仍检索 default 知识库。这个用例锁住 body 里的 agent_id。
    // 用 501 让 streamAgent 在读流之前抛 ApiError：此时 fetch 参数已经拿到。
    const spy = mockFetch(501, { detail: "stop" });

    await expect(
      streamAgent("怎么练", () => {}, undefined, "fitness-coach"),
    ).rejects.toThrow(ApiError);

    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/agent/stream?agent_id=fitness-coach");
    expect(JSON.parse(String(init.body))).toEqual({
      question: "怎么练",
      agent_id: "fitness-coach",
    });
  });

  it("streamAgent 对 default 不带 agent_id（旧路径兼容）", async () => {
    const spy = mockFetch(501, { detail: "stop" });

    await expect(
      streamAgent("苹果", () => {}, undefined, "default"),
    ).rejects.toThrow(ApiError);

    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/agent/stream");
    expect(JSON.parse(String(init.body))).toEqual({ question: "苹果" });
  });
});
