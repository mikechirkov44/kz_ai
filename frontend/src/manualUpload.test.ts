import { describe, expect, it } from "vitest";
import {
  buildManualRows,
  needsSalePrice,
  needsStockDate,
  newManualLine,
  parseOptionalPrice,
  parsePositiveInt,
} from "./manualUpload";

describe("manualUpload", () => {
  it("creates a line with default quantity", () => {
    const line = newManualLine();
    expect(line.quantity).toBe("1");
    expect(line.article).toBe("");
    expect(line.key).toBeTruthy();
  });

  it("parses quantity and price", () => {
    expect(parsePositiveInt("3")).toBe(3);
    expect(parsePositiveInt("0")).toBeNull();
    expect(parsePositiveInt("1.5")).toBeNull();
    expect(parseOptionalPrice("")).toBeUndefined();
    expect(parseOptionalPrice("95 000")).toBe(95000);
    expect(parseOptionalPrice("abc")).toBeNull();
  });

  it("builds payload for one counterparty", () => {
    const { rows, error } = buildManualRows("ТОО Demo", [
      { ...newManualLine(), article: "IM-001", shop: "ЦУМ", quantity: "2", price: "1000" },
    ]);
    expect(error).toBe("");
    expect(rows).toEqual([
      { counterparty: "ТОО Demo", article: "IM-001", shop: "ЦУМ", quantity: 2, price: 1000 },
    ]);
  });

  it("requires counterparty and article", () => {
    expect(buildManualRows("", [newManualLine()]).error).toMatch(/контрагента/);
    expect(buildManualRows("ТОО Demo", [newManualLine()]).error).toMatch(/артикул/);
    expect(buildManualRows("ТОО Demo", []).error).toMatch(/строку/);
  });

  it("flags period fields by type", () => {
    expect(needsStockDate("stocks")).toBe(true);
    expect(needsStockDate("sales")).toBe(false);
    expect(needsSalePrice("both")).toBe(true);
    expect(needsSalePrice("promo_motivation")).toBe(false);
  });
});
