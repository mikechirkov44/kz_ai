import { describe, expect, it } from "vitest";
import { formatCbrChange, formatCbrRate } from "./components/CbrRates";

describe("cbrRates", () => {
  it("formats rates and percent", () => {
    expect(formatCbrRate(86.89)).toBe("86,89 ₽");
    expect(formatCbrRate(0.1852)).toBe("0,1852 ₽");
    expect(formatCbrChange(-0.13)).toBe("−0,13%");
    expect(formatCbrChange(0.23)).toBe("+0,23%");
    expect(formatCbrChange(null)).toBe("—");
  });
});
