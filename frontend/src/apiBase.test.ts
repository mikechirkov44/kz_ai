import { describe, expect, it } from "vitest";
import { resolveApiBaseUrl } from "./api";

describe("resolveApiBaseUrl", () => {
  it("uses localhost in Vite dev when the env is unset", () => {
    expect(resolveApiBaseUrl(undefined)).toBe("http://localhost:8000");
  });

  it("keeps an empty value so production can call same-origin /api", () => {
    expect(resolveApiBaseUrl("")).toBe("");
  });

  it("uses same-origin in production when the env is unset", () => {
    expect(resolveApiBaseUrl(undefined, true)).toBe("");
  });

  it("strips a trailing slash", () => {
    expect(resolveApiBaseUrl("https://vm.example/")).toBe("https://vm.example");
  });
});
