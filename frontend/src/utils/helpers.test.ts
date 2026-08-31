import { describe, expect, it, vi } from "vitest";
import { uuid } from "./helpers";

const UUID_V4_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("uuid", () => {
  it("生成合法 v4 格式的 UUID（版本位=4、变体位∈{8,9,a,b}）", () => {
    expect(uuid()).toMatch(UUID_V4_RE);
  });

  it("两次调用返回不同值", () => {
    expect(uuid()).not.toBe(uuid());
  });

  it("无 crypto 环境（旧 WebView 兜底路径）仍生成合法 v4", () => {
    vi.stubGlobal("crypto", undefined);
    try {
      expect(uuid()).toMatch(UUID_V4_RE);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});