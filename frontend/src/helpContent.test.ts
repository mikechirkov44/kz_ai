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
      expect(
        tab.blocks.some(
          (block) => (block.steps?.length || 0) + (block.notes?.length || 0) + (block.lead ? 1 : 0) > 0,
        ),
      ).toBe(true);
    }
    expect(helpTabById("input").label).toBe("Ввод данных");
    expect(JSON.stringify(helpTabById("input"))).toContain("список ошибок откроет");
    expect(JSON.stringify(helpTabById("reports"))).toContain("Промежуточные");
    expect(JSON.stringify(helpTabById("input"))).toContain("Контрагент, Артикул, Количество");
  });

  it("explains two data sources and shipment fact", () => {
    const start = helpTabById("start");
    const reports = helpTabById("reports");
    const startText = JSON.stringify(start);
    const reportsText = JSON.stringify(reports);
    expect(startText).toContain("Из 1С");
    expect(startText).toContain("Из загрузок менеджера");
    expect(reports.blocks.some((block) => block.title === "Факт отгрузок")).toBe(true);
    expect(reportsText).toContain("тенге");
    expect(reportsText).toContain("звёздочкой");
    expect(reportsText).toContain("подчинённого");
    expect(reportsText).toContain("без звёздочки");
    expect(reportsText).toContain("текущий квартал");
    expect(reportsText).toContain("переложить");
    expect(reportsText).toContain("3 месяца");
    expect(reportsText).toContain("аналитический отчёт");
  });

  it("names receipt journals as in 1C", () => {
    const onec = JSON.stringify(helpTabById("onec"));
    expect(onec).toContain("Поступление продукции из производства");
    expect(onec).toContain("Поступление товаров и услуг");
  });
});
