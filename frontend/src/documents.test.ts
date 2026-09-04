import { describe, expect, it } from "vitest";
import { docTypeLabel, documentTotalQuantity, linesQuantity } from "./documents";

describe("documents", () => {
  it("maps API types to Russian labels", () => {
    expect(docTypeLabel("return")).toBe("Возврат");
    expect(docTypeLabel("realization")).toBe("Реализация");
    expect(docTypeLabel("order")).toBe("Заказ");
    expect(docTypeLabel("production")).toBe("Производство");
    expect(docTypeLabel("")).toBe("");
    expect(docTypeLabel("unknown")).toBe("unknown");
  });

  it("sums line quantities and ignores missing API total", () => {
    const lines = [{ quantity: 1 }, { quantity: 1 }, { quantity: 1 }];
    expect(linesQuantity(lines)).toBe(3);
    expect(documentTotalQuantity(0, lines)).toBe(3);
    expect(documentTotalQuantity(undefined, lines)).toBe(3);
    expect(documentTotalQuantity(5, [])).toBe(5);
    expect(documentTotalQuantity(undefined, undefined)).toBe(0);
  });
});
