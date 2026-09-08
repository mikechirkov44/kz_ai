import { describe, expect, it } from "vitest";
import { readStoredPeriod, writeStoredPeriod } from "./storedPeriod";

describe("storedPeriod", () => {
  it("returns fallback when nothing stored", () => {
    localStorage.clear();
    expect(readStoredPeriod("demo", { from: "2026-01-01", to: "2026-03-31" })).toEqual({
      from: "2026-01-01",
      to: "2026-03-31",
    });
  });

  it("round-trips a valid range", () => {
    localStorage.clear();
    writeStoredPeriod("demo", { from: "2025-12-01", to: "2025-12-31" });
    expect(readStoredPeriod("demo", { from: "2026-01-01", to: "2026-01-31" })).toEqual({
      from: "2025-12-01",
      to: "2025-12-31",
    });
  });

  it("ignores broken payload", () => {
    localStorage.setItem("period:demo", "{not json");
    expect(readStoredPeriod("demo", { from: "2026-01-01", to: "2026-01-31" })).toEqual({
      from: "2026-01-01",
      to: "2026-01-31",
    });
  });

  it("ignores invalid dates", () => {
    localStorage.setItem("period:demo", JSON.stringify({ from: "not-a-date", to: "2026-01-31" }));
    expect(readStoredPeriod("demo", { from: "2026-01-01", to: "2026-01-31" })).toEqual({
      from: "2026-01-01",
      to: "2026-01-31",
    });
  });
});
