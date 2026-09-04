import { describe, expect, it } from "vitest";
import { dwellBucketChart, planPercentChart, prettyArticle, recSeverityChart, workTypeChart } from "./dashboardCharts";

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
      "Высокий",
      "Низкий",
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
});
