import { describe, expect, it } from "vitest";
import { formatDetailValue, visibleDetailRows } from "./nomenclatureDetails";

describe("nomenclatureDetails", () => {
  it("hides empty rows and keeps always-visible ones", () => {
    expect(formatDetailValue(true)).toBe("да");
    expect(formatDetailValue(null)).toBe("—");
    expect(
      visibleDetailRows([
        { label: "Артикул", value: "K1", always: true },
        { label: "Штрихкод", value: "" },
        { label: "Комплект", value: "4264-120" },
        { label: "Акция", value: false, always: true },
      ]),
    ).toEqual([
      { label: "Артикул", text: "K1", always: true },
      { label: "Комплект", text: "4264-120", always: false },
      { label: "Акция", text: "нет", always: true },
    ]);
  });
});
