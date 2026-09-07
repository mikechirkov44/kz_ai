import { describe, expect, it } from "vitest";
import type { SummaryClient } from "./components/QuarterlyMatrix";
import {
  filterQuarterlyClients,
  hasQuarterlyDetail,
  uniqueManagers,
  uniqueWorkTypes,
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

  it("uniqueWorkTypes and uniqueManagers", () => {
    expect(uniqueWorkTypes([withDetail, emptyOnly])).toEqual(["Рост", "Удержание"]);
    expect(uniqueWorkTypes([withDetail, client({ counterparty: "X", work_type_label: "—" })])).toEqual([
      "Удержание",
    ]);
    expect(uniqueManagers([withDetail, emptyOnly])).toEqual(["Иванов"]);
  });
});
