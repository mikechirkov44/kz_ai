import { describe, expect, it } from "vitest";
import type { SummaryClient } from "./components/QuarterlyMatrix";
import { recCellLines, recTableLine } from "./components/QuarterlyMatrix";
import {
  filterQuarterlyClients,
  filterResultsClients,
  formatDynamicsValue,
  formatValueWithTrend,
  hasQuarterlyDetail,
  totalPlanRow,
  totalResultsClient,
  totalSummaryClient,
  isQuarterlyTab,
  QUARTERLY_TABS,
  shouldLoadQuarterlyResults,
  shouldLoadQuarterlySummary,
  trendClass,
  uniqueManagers,
  uniqueWorkTypes,
  type ResultsClient,
} from "./quarterlyFilters";

function client(partial: Partial<SummaryClient> & { counterparty: string }): SummaryClient {
  return {
    counterparty_id: partial.counterparty_id || partial.counterparty,
    plan: 0,
    sales_prev_quarter: 0,
    sales_prev2_quarter: 0,
    dynamics_percent: null,
    comment: null,
    next_quarter_plan: 0,
    recommendations_text: "",
    matrix: [],
    ...partial,
  };
}

describe("quarterlyFilters", () => {
  const withDetail = client({
    counterparty: "ИП Almaz-A",
    work_type_label: "Удержание",
    manager_name: "Иванов",
    matrix: [{ metal_color: { dimension: "Красное", avg_stock: 1, sales_total: 2, quarter_turnover_percent: 3, avg_month_turnover_percent: 1 } }],
  });
  const emptyOnly = client({
    counterparty: "Гранат",
    work_type_label: "Рост",
    matrix: [{ is_total: true }],
  });

  it("hasQuarterlyDetail ignores total-only matrix", () => {
    expect(hasQuarterlyDetail(withDetail)).toBe(true);
    expect(hasQuarterlyDetail(emptyOnly)).toBe(false);
  });

  it("hides empty clients by default and filters by name/type/manager", () => {
    const rows = [withDetail, emptyOnly];
    expect(filterQuarterlyClients(rows).map((c) => c.counterparty)).toEqual(["ИП Almaz-A"]);
    expect(filterQuarterlyClients(rows, { includeEmpty: true }).map((c) => c.counterparty)).toEqual([
      "ИП Almaz-A",
      "Гранат",
    ]);
    expect(filterQuarterlyClients(rows, { query: "almaz" }).map((c) => c.counterparty)).toEqual(["ИП Almaz-A"]);
    expect(filterQuarterlyClients(rows, { includeEmpty: true, workType: "Рост" }).map((c) => c.counterparty)).toEqual([
      "Гранат",
    ]);
    expect(filterQuarterlyClients(rows, { manager: "иван" }).map((c) => c.counterparty)).toEqual(["ИП Almaz-A"]);
  });

  it("lists quarterly page tabs", () => {
    expect(QUARTERLY_TABS.map((tab) => tab.id)).toEqual(["progress", "results", "summary", "plan"]);
    expect(isQuarterlyTab("summary")).toBe(true);
    expect(isQuarterlyTab("results")).toBe(true);
    expect(isQuarterlyTab("other")).toBe(false);
    expect(shouldLoadQuarterlySummary("summary")).toBe(true);
    expect(shouldLoadQuarterlySummary("progress")).toBe(false);
    expect(shouldLoadQuarterlySummary("plan")).toBe(false);
    expect(shouldLoadQuarterlyResults("results")).toBe(true);
    expect(shouldLoadQuarterlyResults("summary")).toBe(false);
  });

  it("uniqueWorkTypes and uniqueManagers", () => {
    expect(uniqueWorkTypes([withDetail, emptyOnly])).toEqual(["Рост", "Удержание"]);
    expect(uniqueWorkTypes([withDetail, client({ counterparty: "X", work_type_label: "—" })])).toEqual([
      "Удержание",
    ]);
    expect(uniqueManagers([withDetail, emptyOnly])).toEqual(["Иванов"]);
  });

  it("filterResultsClients keeps zeros and filters by name/type/manager", () => {
    const withPlan: ResultsClient = {
      counterparty_id: "1",
      counterparty: "ИП Almaz-A",
      manager_name: "Иванов",
      work_type_label: "Удержание",
      plan: 50,
      shipment_fact: 10,
      shipment_percent: 20,
      shipment_prev_quarter: 0,
      shipment_prev2_quarter: 0,
      shipment_dynamics_percent: null,
      sales_total: 0,
      sales_prev_quarter: 0,
      sales_prev2_quarter: 0,
      dynamics_percent: null,
      comment: null,
    };
    const zeroPlan: ResultsClient = {
      ...withPlan,
      counterparty_id: "2",
      counterparty: "Гранат",
      manager_name: "Петров",
      work_type_label: "Рост",
      plan: 0,
    };
    expect(filterResultsClients([withPlan, zeroPlan]).map((c) => c.counterparty)).toEqual(["ИП Almaz-A", "Гранат"]);
    expect(filterResultsClients([withPlan, zeroPlan], { query: "almaz" }).map((c) => c.counterparty)).toEqual([
      "ИП Almaz-A",
    ]);
    expect(filterResultsClients([withPlan, zeroPlan], { workType: "Рост" }).map((c) => c.counterparty)).toEqual([
      "Гранат",
    ]);
    expect(filterResultsClients([withPlan, zeroPlan], { manager: "петр" }).map((c) => c.counterparty)).toEqual([
      "Гранат",
    ]);
  });

  it("totals quarterly plan and results rows", () => {
    const plans = [
      { counterparty: "A", counterparty_id: "1", plan: 100, fact: 50, percent: 50 },
      { counterparty: "B", counterparty_id: "2", plan: 20, fact: 40, percent: 200 },
    ];
    const planTotal = totalPlanRow(plans);
    expect(planTotal.counterparty).toBe("Итого");
    expect(planTotal.plan).toBe(120);
    expect(planTotal.fact).toBe(90);
    expect(planTotal.percent).toBe(75);

    const results: ResultsClient[] = [
      {
        counterparty_id: "1",
        counterparty: "A",
        plan: 100,
        shipment_fact: 50,
        shipment_percent: 50,
        shipment_prev_quarter: 25,
        shipment_prev2_quarter: 10,
        shipment_dynamics_percent: 200,
        sales_total: 10,
        sales_prev_quarter: 5,
        sales_prev2_quarter: 4,
        dynamics_percent: 200,
        comment: null,
      },
      {
        counterparty_id: "2",
        counterparty: "B",
        plan: 0,
        shipment_fact: 10,
        shipment_percent: 0,
        shipment_prev_quarter: 5,
        shipment_prev2_quarter: 0,
        shipment_dynamics_percent: 200,
        sales_total: 6,
        sales_prev_quarter: 3,
        sales_prev2_quarter: 1,
        dynamics_percent: 200,
        comment: null,
      },
    ];
    const resultTotal = totalResultsClient(results);
    expect(resultTotal.plan).toBe(100);
    expect(resultTotal.shipment_fact).toBe(60);
    expect(resultTotal.shipment_percent).toBe(60);
    expect(resultTotal.sales_total).toBe(16);
    expect(resultTotal.dynamics_percent).toBe(200);
  });

  it("totals summary matrix by category including Кольцо and Серьги", () => {
    const total = totalSummaryClient([
      client({
        counterparty: "Гранат",
        plan: 10,
        sales_total: 6,
        sales_prev_quarter: 2,
        matrix: [
          {
            wear_type: { dimension: "Кольцо", avg_stock: 4, sales_total: 2, quarter_turnover_percent: 50, avg_month_turnover_percent: 16 },
            metal_color: { dimension: "Белое", avg_stock: 4, sales_total: 2, quarter_turnover_percent: 50, avg_month_turnover_percent: 16 },
          },
          {
            wear_type: { dimension: "Серьги", avg_stock: 8, sales_total: 4, quarter_turnover_percent: 50, avg_month_turnover_percent: 16 },
            metal_color: { dimension: "Лимонное", avg_stock: 8, sales_total: 4, quarter_turnover_percent: 50, avg_month_turnover_percent: 16 },
          },
          {
            is_total: true,
            metal_color: { dimension: "Итого", avg_stock: 12, sales_total: 6, quarter_turnover_percent: 50, avg_month_turnover_percent: 16 },
          },
        ],
      }),
    ]);
    const wears = total.matrix.filter((row) => !row.is_total).map((row) => row.wear_type?.dimension);
    expect(wears).toEqual(["Кольцо", "Серьги"]);
    expect(total.matrix.some((row) => row.is_total && row.wear_type?.sales_total === 6)).toBe(true);
    expect(total.plan).toBe(10);
  });

  it("formatValueWithTrend and trendClass", () => {
    expect(formatValueWithTrend("80%", "Падение")).toBe("80% Падение");
    expect(formatValueWithTrend("—", "Рост")).toBe("Рост");
    expect(trendClass("Рост")).toBe("dyn-up");
    expect(trendClass("Нестабильный")).toBe("dyn-unstable");
    expect(trendClass(null)).toBe("");
    expect(formatDynamicsValue(2.03, "Рост")).toBe("203% к пред. Рост");
    expect(formatDynamicsValue(0.63, "Нестабильный")).toBe("63% к пред. Нестабильный");
  });
});

describe("rec table lines", () => {
  it("prefers llm comment then title and splits cell text", () => {
    expect(
      recTableLine({
        message: "длинный текст",
        title: "Довезите кольца",
        llm_comment: "Позвоните и заберите серьги",
      }),
    ).toBe("Позвоните и заберите серьги");
    expect(recTableLine({ message: "длинный текст", title: "Довезите кольца" })).toBe("Довезите кольца");
    expect(recCellLines("Верните 2 SKU · Довезите кольца")).toEqual(["Верните 2 SKU", "Довезите кольца"]);
    expect(recCellLines("", [{ message: "длинный", title: "Коротко" }])).toEqual(["Коротко"]);
  });
});
