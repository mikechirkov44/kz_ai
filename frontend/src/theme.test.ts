import { afterEach, describe, expect, it } from "vitest";
import { applyTheme, isThemeId, readTheme, THEME_KEY } from "./theme";

describe("theme", () => {
  afterEach(() => {
    localStorage.removeItem(THEME_KEY);
    document.documentElement.removeAttribute("data-theme");
  });

  it("accepts known ids", () => {
    expect(isThemeId("emerald")).toBe(true);
    expect(isThemeId("dark")).toBe(true);
    expect(isThemeId("pink")).toBe(false);
  });

  it("applies and reads theme", () => {
    expect(readTheme()).toBe("emerald");
    applyTheme("indigo");
    expect(document.documentElement.getAttribute("data-theme")).toBe("indigo");
    expect(readTheme()).toBe("indigo");
  });
});
