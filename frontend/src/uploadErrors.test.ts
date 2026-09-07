import { describe, expect, it } from "vitest";
import { hasUploadErrors, uploadErrorSubtitle } from "./uploadErrors";

describe("uploadErrors", () => {
  it("detects a non-empty error list", () => {
    expect(hasUploadErrors([])).toBe(false);
    expect(hasUploadErrors(undefined)).toBe(false);
    expect(hasUploadErrors([{ row: 2, field: "article", message: "Нет в справочнике" }])).toBe(true);
  });

  it("summarizes processed rows and error count", () => {
    expect(uploadErrorSubtitle(12, [{ row: 3, field: "qty", message: "Не целое" }])).toBe(
      "Обработано 12, ошибок 1",
    );
  });
});
