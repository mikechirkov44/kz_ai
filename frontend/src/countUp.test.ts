import { describe, expect, it } from "vitest";
import { countUpValue, easeOutCubic } from "./countUp";

describe("countUp", () => {
  it("eases from 0 to 1", () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5);
    expect(easeOutCubic(-1)).toBe(0);
    expect(easeOutCubic(2)).toBe(1);
  });

  it("interpolates toward the target", () => {
    expect(countUpValue(0, 100, 0)).toBe(0);
    expect(countUpValue(0, 100, 1)).toBe(100);
    expect(countUpValue(10, 20, 1)).toBe(20);
    expect(countUpValue(0, 10, 0.5)).toBeGreaterThan(5);
  });
});
