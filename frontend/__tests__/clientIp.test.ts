import { describe, expect, it } from "vitest";

import { clientIpOf, trustedHops } from "@/lib/clientIp";

// XFF 可信性：只有最右侧由我们自己的代理追加的项可信，
// 左侧全部由客户端控制，可以随意伪造。

describe("clientIpOf", () => {
  it("默认 1 跳时取最右侧 IP", () => {
    expect(clientIpOf("6.6.6.6, 1.2.3.4", 1)).toBe("1.2.3.4");
  });

  it("层数不足时返回空串，而不是退化成不可信的值", () => {
    expect(clientIpOf("1.2.3.4", 2)).toBe("");
  });

  it("没有 XFF 时返回空串", () => {
    expect(clientIpOf(null, 1)).toBe("");
    expect(clientIpOf("", 1)).toBe("");
  });

  it("忽略空段与多余空白", () => {
    expect(clientIpOf(" 6.6.6.6 ,  , 1.2.3.4 ", 1)).toBe("1.2.3.4");
    expect(clientIpOf("6.6.6.6, ,1.2.3.4", 2)).toBe("6.6.6.6");
  });

  it("两跳代理时取右数第二个", () => {
    // 客户端可伪造最左侧，最右两项由我们的两层代理写入
    expect(clientIpOf("9.9.9.9, 5.5.5.5, 1.2.3.4", 2)).toBe("5.5.5.5");
  });
});

describe("trustedHops", () => {
  it("默认 1", () => {
    delete process.env.TRUSTED_PROXY_HOPS;
    expect(trustedHops()).toBe(1);
  });

  it("读取环境变量", () => {
    process.env.TRUSTED_PROXY_HOPS = "2";
    expect(trustedHops()).toBe(2);
    delete process.env.TRUSTED_PROXY_HOPS;
  });

  it("非法值回退为 1", () => {
    for (const bad of ["0", "-1", "abc", "1.5", ""]) {
      process.env.TRUSTED_PROXY_HOPS = bad;
      expect(trustedHops()).toBe(1);
    }
    delete process.env.TRUSTED_PROXY_HOPS;
  });
});
