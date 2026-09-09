import { describe, expect, it } from "vitest";
import type { SummaryClient } from "./components/QuarterlyMatrix";
import {
  filterQuarterlyClients,
  filterResultsClients,
  hasQuarterlyDetail,
  isQuarterlyTab,
  QUARTERLY_TABS,
  shouldLoadQuarterlyResults,
  shouldLoadQuarterlySummary,
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
});
