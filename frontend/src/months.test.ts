import { describe, expect, it } from "vitest";
import { monthClickPeriod, monthRange, parseRuDate, quarterRange, snapPeriod, yearMonthFromIso, yearQuarterFromIso, yearRange } from "./months";

describe("months", () => {
  it("monthRange covers the last day", () => {
    expect(monthRange(2023, 2)).toEqual({ from: "2023-02-01", to: "2023-02-28" });
    expect(monthRange(2024, 2)).toEqual({ from: "2024-02-01", to: "2024-02-29" });
  });

  it("quarterRange maps Q1–Q4", () => {
    expect(quarterRange(2023, 1)).toEqual({ from: "2023-01-01", to: "2023-03-31" });
    expect(quarterRange(2023, 4)).toEqual({ from: "2023-10-01", to: "2023-12-31" });
  });

  it("yearRange is calendar year", () => {
    expect(yearRange(2025)).toEqual({ from: "2025-01-01", to: "2025-12-31" });
  });

  it("yearQuarterFromIso", () => {
    expect(yearQuarterFromIso("2023-01-01")).toEqual({ year: 2023, quarter: 1 });
    expect(yearQuarterFromIso("2026-09-04")).toEqual({ year: 2026, quarter: 3 });
    expect(yearQuarterFromIso("bad")).toEqual({ year: new Date().getFullYear(), quarter: 1 });
  });

  it("yearMonthFromIso", () => {
    expect(yearMonthFromIso("2023-01-01")).toEqual({ year: 2023, month: 1 });
    expect(yearMonthFromIso("2026-09-04")).toEqual({ year: 2026, month: 9 });
  });

  it("parseRuDate and snapPeriod", () => {
    expect(parseRuDate("04.09.2026")).toBe("2026-09-04");
    expect(parseRuDate("31.02.2026")).toBeNull();
    expect(snapPeriod("2026-09-04", "2026-09-01", "range")).toEqual({ from: "2026-09-01", to: "2026-09-04" });
    expect(snapPeriod("2026-09-04", "2026-11-10", "month")).toEqual(monthRange(2026, 9));
    expect(snapPeriod("2026-09-04", "2026-11-10", "quarter")).toEqual(quarterRange(2026, 3));
    expect(snapPeriod("2026-01-15", "2026-03-02", "month-range")).toEqual({ from: "2026-01-01", to: "2026-03-31" });
  });

  it("monthClickPeriod", () => {
    const first = monthClickPeriod("range", 2026, 9, "2026-01-01", false);
    expect(first).toEqual({ from: "2026-09-01", to: "2026-09-30", pickingEnd: true });
    const second = monthClickPeriod("range", 2026, 11, first.from, true);
    expect(second).toEqual({ from: "2026-09-01", to: "2026-11-30", pickingEnd: false });
    expect(monthClickPeriod("month", 2023, 1, "", false)).toEqual({
      from: "2023-01-01",
      to: "2023-01-31",
      pickingEnd: false,
    });
    expect(monthClickPeriod("quarter", 2023, 2, "", false)).toEqual({
      from: "2023-01-01",
      to: "2023-03-31",
      pickingEnd: false,
    });
  });
});
