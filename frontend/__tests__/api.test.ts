import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, ask, deleteDoc, listDocs, uploadDoc } from "@/lib/api";

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
    expect(init.headers).toBeUndefined();
  });

  it("删除请求对 doc_id 做 URL 编码", async () => {
    const spy = mockFetch(200, { status: "ok", doc_id: "a b", filename: "a.txt" });

    await deleteDoc("a b");

    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/docs/a%20b");
    expect(init.method).toBe("DELETE");
  });
});
