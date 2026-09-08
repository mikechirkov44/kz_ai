import { describe, expect, it } from "vitest";
import { formatWorkTypePercent, workTypeLabel } from "./workType";

describe("workTypeLabel", () => {
  it("maps 1C and internal names to Рост / Удержание / Падение", () => {
    expect(workTypeLabel("Прирост")).toBe("Рост");
    expect(workTypeLabel("growth")).toBe("Рост");
    expect(workTypeLabel("Удержание")).toBe("Удержание");
    expect(workTypeLabel("hold")).toBe("Удержание");
    expect(workTypeLabel("падение")).toBe("Падение");
    expect(workTypeLabel(null)).toBe("—");
    expect(workTypeLabel("")).toBe("—");
  });
});

describe("formatWorkTypePercent", () => {
  it("adds a percent sign", () => {
    expect(formatWorkTypePercent(15)).toBe("15%");
    expect(formatWorkTypePercent(0)).toBe("0%");
    expect(formatWorkTypePercent(null)).toBe("—");
  });
});
