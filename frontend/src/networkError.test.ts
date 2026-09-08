import { describe, expect, it } from "vitest";
import { networkErrorMessage } from "./networkError";

describe("networkErrorMessage", () => {
  it("explains a failed fetch", () => {
    expect(networkErrorMessage(new TypeError("Failed to fetch"))).toContain("Нет связи с сервером");
  });

  it("explains an aborted request", () => {
    const abort = new Error("Aborted");
    abort.name = "AbortError";
    expect(networkErrorMessage(abort)).toBe("Запрос отменён");
  });

  it("keeps a regular error text", () => {
    expect(networkErrorMessage(new Error("Нет доступа"))).toBe("Нет доступа");
  });
});
