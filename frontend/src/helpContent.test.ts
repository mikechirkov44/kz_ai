import { describe, expect, it } from "vitest";
import { defaultHelpTab, HELP_TABS, helpTabById } from "./helpContent";

describe("helpContent", () => {
  it("opens the right tab for each role", () => {
    expect(defaultHelpTab("manager")).toBe("input");
    expect(defaultHelpTab("analytic")).toBe("reports");
    expect(defaultHelpTab("regional_director")).toBe("reports");
    expect(defaultHelpTab("admin")).toBe("admin");
    expect(defaultHelpTab(null)).toBe("start");
  });

  it("has six tabs with steps or notes", () => {
    expect(HELP_TABS.map((tab) => tab.id)).toEqual(["start", "input", "reports", "onec", "roles", "admin"]);
    for (const tab of HELP_TABS) {
      expect(tab.blocks.length).toBeGreaterThan(0);
      expect(tab.blocks.some((block) => (block.steps?.length || 0) + (block.notes?.length || 0) > 0)).toBe(true);
    }
    expect(helpTabById("input").label).toBe("Ввод данных");
  });
});
