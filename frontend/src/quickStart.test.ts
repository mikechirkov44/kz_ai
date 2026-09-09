import { afterEach, describe, expect, it } from "vitest";
import {
  allowedQuickStartTools,
  defaultQuickStartPaths,
  QUICK_START_KEY_PREFIX,
  readQuickStartPaths,
  sanitizeQuickStartPaths,
  writeQuickStartPaths,
} from "./quickStart";

describe("quickStart", () => {
  afterEach(() => {
    localStorage.removeItem(`${QUICK_START_KEY_PREFIX}u1`);
  });

  it("hides admin tools from managers", () => {
    expect(allowedQuickStartTools("manager").some((t) => t.to === "/admin")).toBe(false);
    expect(allowedQuickStartTools("admin").some((t) => t.to === "/admin")).toBe(true);
  });

  it("uses role presets", () => {
    expect(defaultQuickStartPaths("manager")).toEqual([
      "/uploads",
      "/quarterly",
      "/motivation",
      "/recommendations",
    ]);
    expect(defaultQuickStartPaths("admin")[0]).toBe("/admin");
  });

  it("drops unknown and admin-only paths", () => {
    expect(sanitizeQuickStartPaths(["/admin", "/quarterly", "/nope"], "manager")).toEqual(["/quarterly"]);
  });

  it("stores and reads per user", () => {
    writeQuickStartPaths("u1", ["/turnover", "/fact"], "analytic");
    expect(readQuickStartPaths("u1", "analytic")).toEqual(["/turnover", "/fact"]);
  });
});
