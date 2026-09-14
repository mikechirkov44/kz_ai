import { describe, expect, it } from "vitest";
import { dwellBucketChart, planPercentChart, prettyArticle, recSeverityChart, topSalesByCounterparty, topSalesByManager, weekRangeLabel, weeklyPlanChart, currentWeeklyBar, workTypeChart } from "./dashboardCharts";

describe("dashboardCharts", () => {
  it("workTypeChart skips empty buckets", () => {
    const rows = workTypeChart([
      { work_type: "hold" },
      { work_type: "hold" },
      { work_type: "growth" },
      { work_type: null },
    ]);
    expect(rows.map((r) => r.name)).toEqual(["Удержание", "Рост", "Не задан"]);
    expect(rows[0].value).toBe(2);
  });

  it("dwellBucketChart and recSeverityChart", () => {
    const dwell = dwellBucketChart([
      { months_without_sales: 0 },
      { months_without_sales: 7 },
      { months_without_sales: 7 },
    ]);
    expect(dwell).toEqual([
      { name: "0–1 мес.", value: 1, fill: "#059669" },
      { name: "7+", value: 2, fill: "#dc2626" },
    ]);
    expect(recSeverityChart([{ severity: "high" }, { severity: "low" }]).map((r) => r.name)).toEqual([
      "Срочно",
      "На заметку",
    ]);
  });

  it("planPercentChart sorts ascending", () => {
    const rows = planPercentChart(
      [
        { counterparty: "Beta", percent: 120 },
        { counterparty: "Alpha", percent: 40 },
      ],
      10,
    );
    expect(rows[0]).toEqual({ name: "Alpha", percent: 40 });
    expect(prettyArticle("000001797")).toBe("1797");
  });

  it("topSalesByCounterparty ranks by Excel sales", () => {
    const rows = topSalesByCounterparty(
      [
        { counterparty: "C", sales_total: 10 },
        { counterparty: "A", sales_total: 50 },
        { counterparty: "B", sales_total: 0 },
        { counterparty: "D", sales_total: 20 },
      ],
      2,
    );
    expect(rows).toEqual([
      { name: "A", sales: 50 },
      { name: "D", sales: 20 },
    ]);
  });

  it("topSalesByManager sums clients and skips empty sales", () => {
    const rows = topSalesByManager([
      { counterparty: "a", manager_name: "Иванов", sales_total: 10 },
      { counterparty: "b", manager_name: "Иванов", sales_total: 5 },
      { counterparty: "c", manager_name: "Петров", sales_total: 12 },
      { counterparty: "d", manager_name: null, sales_total: 3 },
      { counterparty: "e", manager_name: "Петров", sales_total: 0 },
    ]);
    expect(rows.map((r) => r.name)).toEqual(["Иванов", "Петров", "Без менеджера"]);
    expect(rows[0].sales).toBe(15);
    expect(rows[1].sales).toBe(12);
    expect(rows[2].sales).toBe(3);
  });

  it("weekRangeLabel and weeklyPlanChart", () => {
    expect(weekRangeLabel("2026-07-01", "2026-07-05")).toBe("1–5 июл");
    expect(weekRangeLabel("2026-09-28", "2026-09-30")).toBe("28–30 сен");
    expect(weekRangeLabel("2026-03-30", "2026-04-02")).toBe("30 мар–2 апр");
    const rows = weeklyPlanChart([
      {
        week_index: 1,
        week_start: "2026-07-01",
        week_end: "2026-07-05",
        days: 5,
        plan: "100.00",
        fact: "40",
        percent: "40.00",
        is_current: false,
      },
      {
        week_index: 2,
        week_start: "2026-07-06",
        week_end: "2026-07-12",
        days: 7,
        plan: 140,
        fact: 0,
        percent: 0,
        is_current: true,
      },
    ]);
    expect(rows[0]).toEqual({
      name: "Н1",
      label: "1–5 июл",
      plan: 100,
      fact: 40,
      percent: 40,
      isCurrent: false,
    });
    expect(currentWeeklyBar(rows)?.name).toBe("Н2");
  });
});
