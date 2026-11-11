import { describe, expect, it } from "vitest";
import { parseError } from "./api";

describe("parseError", () => {
  it("replaces an nginx 504 page", () => {
    const html = "<html><head><title>504 Gateway Time-out</title></head><body>504</body></html>";
    expect(parseError(html, 504)).toBe("Сервер не успел посчитать отчёт");
  });

  it("hides other html error pages", () => {
    expect(parseError("<html><title>502</title></html>", 502)).toBe("Ошибка 502");
  });

  it("keeps a json detail", () => {
    expect(parseError(JSON.stringify({ detail: "Нет данных" }), 400)).toBe("Нет данных");
  });
});
