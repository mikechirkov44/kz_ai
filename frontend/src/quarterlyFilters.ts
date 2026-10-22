import type { SummaryClient } from "./components/QuarterlyMatrix";

export type QuarterlyTab = "progress" | "results" | "summary" | "plan";

export const QUARTERLY_TABS: { id: QuarterlyTab; label: string }[] = [
  { id: "progress", label: "Промежуточные" },
  { id: "results", label: "Итоги квартала" },
  { id: "summary", label: "Итог" },
  { id: "plan", label: "План" },
];

export type ResultsClient = {
  counterparty_id: string;
  counterparty: string;
  manager_name?: string | null;
  work_type?: string | null;
  work_type_label?: string | null;
  work_type_percent?: number | null;
  plan: number;
  shipment_fact: number;
  shipment_percent: number;
  shipment_prev_quarter: number;
  shipment_prev2_quarter: number;
  shipment_dynamics_percent: number | null;
  shipment_dynamics_trend?: string | null;
  sales_total: number;
  sales_prev_quarter: number;
  sales_prev2_quarter: number;
  dynamics_percent: number | null;
  dynamics_trend?: string | null;
  comment: string | null;
};

export type ResultsLabels = {
  plan?: string;
  shipment_fact?: string;
  shipment_percent?: string;
  shipment_prev?: string;
  shipment_prev2?: string;
  shipment_dynamics?: string;
  sales?: string;
  sales_prev?: string;
  sales_prev2?: string;
  sales_dynamics?: string;
};

export function isQuarterlyTab(value: string): value is QuarterlyTab {
  return QUARTERLY_TABS.some((tab) => tab.id === value);
}

export function shouldLoadQuarterlySummary(tab: QuarterlyTab): boolean {
  return tab === "summary";
}

export function shouldLoadQuarterlyResults(tab: QuarterlyTab): boolean {
  return tab === "results";
}

export function hasQuarterlyDetail(client: SummaryClient): boolean {
  return (client.matrix || []).some((row) => !row.is_total);
}

export function filterQuarterlyClients(
  clients: SummaryClient[],
  opts: { query?: string; workType?: string; manager?: string; includeEmpty?: boolean } = {},
): SummaryClient[] {
  const query = (opts.query || "").trim().toLowerCase();
  const workType = (opts.workType || "").trim().toLowerCase();
  const manager = (opts.manager || "").trim().toLowerCase();
  return clients.filter((client) => {
    if (!opts.includeEmpty && !hasQuarterlyDetail(client)) return false;
    if (query && !client.counterparty.toLowerCase().includes(query)) return false;
    const work = (client.work_type_label || client.work_type || "").toLowerCase();
    if (workType && work !== workType) return false;
    const mgr = (client.manager_name || "").toLowerCase();
    if (manager && !mgr.includes(manager)) return false;
    return true;
  });
}

export function filterResultsClients(
  clients: ResultsClient[],
  opts: { query?: string; workType?: string; manager?: string } = {},
): ResultsClient[] {
  const query = (opts.query || "").trim().toLowerCase();
  const workType = (opts.workType || "").trim().toLowerCase();
  const manager = (opts.manager || "").trim().toLowerCase();
  return clients.filter((client) => {
    if (query && !client.counterparty.toLowerCase().includes(query)) return false;
    const work = (client.work_type_label || client.work_type || "").toLowerCase();
    if (workType && work !== workType) return false;
    const mgr = (client.manager_name || "").toLowerCase();
    if (manager && !mgr.includes(manager)) return false;
    return true;
  });
}

export const TOTAL_ROW_ID = "__total__";

function num(value: number | null | undefined): number {
  return Number(value) || 0;
}

function percent(fact: number, plan: number): number {
  if (!plan) return 0;
  return Math.round((fact / plan) * 10000) / 100;
}

export type PlanTotalRow = {
  counterparty: string;
  counterparty_id: string;
  plan: number;
  fact: number;
  percent: number;
  dynamics?: number | null;
  dynamics_trend?: string | null;
  manager_name?: string | null;
  work_type?: string | null;
  work_type_label?: string | null;
  work_type_percent?: number | null;
};

export function totalPlanRow(rows: PlanTotalRow[]): PlanTotalRow {
  const plan = rows.reduce((sum, row) => sum + num(row.plan), 0);
  const fact = rows.reduce((sum, row) => sum + num(row.fact), 0);
  return {
    counterparty: "Итого",
    counterparty_id: TOTAL_ROW_ID,
    plan,
    fact,
    percent: percent(fact, plan),
    dynamics: null,
    dynamics_trend: null,
    manager_name: "",
    work_type: null,
    work_type_label: "",
    work_type_percent: null,
  };
}

export function totalResultsClient(clients: ResultsClient[]): ResultsClient {
  const plan = clients.reduce((sum, row) => sum + num(row.plan), 0);
  const shipmentFact = clients.reduce((sum, row) => sum + num(row.shipment_fact), 0);
  const shipmentPrev = clients.reduce((sum, row) => sum + num(row.shipment_prev_quarter), 0);
  const shipmentPrev2 = clients.reduce((sum, row) => sum + num(row.shipment_prev2_quarter), 0);
  const sales = clients.reduce((sum, row) => sum + num(row.sales_total), 0);
  const salesPrev = clients.reduce((sum, row) => sum + num(row.sales_prev_quarter), 0);
  const salesPrev2 = clients.reduce((sum, row) => sum + num(row.sales_prev2_quarter), 0);
  const shipDyn = shipmentPrev ? (shipmentFact / shipmentPrev) * 100 : null;
  const salesDyn = salesPrev ? (sales / salesPrev) * 100 : null;
  return {
    counterparty_id: TOTAL_ROW_ID,
    counterparty: "Итого",
    manager_name: "",
    work_type: null,
    work_type_label: "",
    work_type_percent: null,
    plan,
    shipment_fact: shipmentFact,
    shipment_percent: percent(shipmentFact, plan),
    shipment_prev_quarter: shipmentPrev,
    shipment_prev2_quarter: shipmentPrev2,
    shipment_dynamics_percent: shipDyn,
    shipment_dynamics_trend: null,
    sales_total: sales,
    sales_prev_quarter: salesPrev,
    sales_prev2_quarter: salesPrev2,
    dynamics_percent: salesDyn,
    dynamics_trend: null,
    comment: null,
  };
}

function addDim(
  acc: Record<string, { sales: number; avg: number }>,
  dim?: { dimension?: string; sales_total?: number; avg_stock?: number; is_empty?: boolean } | null,
) {
  const name = (dim?.dimension || "").trim();
  if (!name || name === "Итого" || dim?.is_empty) return;
  const cur = acc[name] || { sales: 0, avg: 0 };
  cur.sales += num(dim?.sales_total);
  cur.avg += num(dim?.avg_stock);
  acc[name] = cur;
}

function dimMetrics(name: string, sales: number, avg: number) {
  const qTurn = avg ? (sales / avg) * 100 : 0;
  return {
    dimension: name,
    avg_stock: avg,
    sales_total: sales,
    quarter_turnover_percent: qTurn,
    avg_month_turnover_percent: qTurn / 3,
  };
}

function zipDimRows(
  metal: ReturnType<typeof dimMetrics>[],
  lts: ReturnType<typeof dimMetrics>[],
  wear: ReturnType<typeof dimMetrics>[],
) {
  const n = Math.max(metal.length, lts.length, wear.length);
  return Array.from({ length: n }, (_, idx) => ({
    metal_color: metal[idx],
    lts: lts[idx],
    wear_type: wear[idx],
  }));
}

export function totalSummaryClient(clients: SummaryClient[]): SummaryClient {
  const metal: Record<string, { sales: number; avg: number }> = {};
  const lts: Record<string, { sales: number; avg: number }> = {};
  const wear: Record<string, { sales: number; avg: number }> = {};
  let plan = 0;
  let salesTotal = 0;
  let salesPrev = 0;
  let salesPrev2 = 0;
  let nextPlan = 0;
  for (const client of clients) {
    plan += num(client.plan);
    const totalRow = (client.matrix || []).find((row) => row.is_total);
    salesTotal += num(client.sales_total) || num(totalRow?.metal_color?.sales_total);
    salesPrev += num(client.sales_prev_quarter);
    salesPrev2 += num(client.sales_prev2_quarter);
    nextPlan += num(client.next_quarter_plan);
    for (const row of client.matrix || []) {
      if (row.is_total) continue;
      addDim(metal, row.metal_color);
      addDim(lts, row.lts);
      addDim(wear, row.wear_type);
    }
  }
  const byName = (left: string, right: string) => left.localeCompare(right, "ru");
  const metalRows = Object.entries(metal)
    .sort(([a], [b]) => byName(a, b))
    .map(([name, value]) => dimMetrics(name, value.sales, value.avg));
  const ltsRows = Object.entries(lts)
    .sort(([a], [b]) => byName(a, b))
    .map(([name, value]) => dimMetrics(name, value.sales, value.avg));
  const wearNames = new Set<string>([
    ...Object.keys(wear),
    ...clients.flatMap((client) =>
      (client.matrix || [])
        .map((row) => row.wear_type?.dimension || "")
        .filter((name) => name && name !== "Итого"),
    ),
  ]);
  const wearRows = [...wearNames]
    .sort(byName)
    .map((name) =>
      wear[name]
        ? dimMetrics(name, wear[name].sales, wear[name].avg)
        : {
            dimension: name,
            avg_stock: null,
            sales_total: null,
            quarter_turnover_percent: null,
            avg_month_turnover_percent: null,
            is_empty: true,
          },
    );
  const totalAvg = clients.reduce((sum, client) => {
    const row = (client.matrix || []).find((item) => item.is_total);
    return sum + num(row?.metal_color?.avg_stock);
  }, 0);
  const metalSales = Object.values(metal).reduce((sum, value) => sum + value.sales, 0);
  const grandSales = salesTotal || metalSales;
  const total = dimMetrics("Итого", grandSales, totalAvg);
  return {
    counterparty_id: TOTAL_ROW_ID,
    counterparty: "Итого",
    plan,
    sales_total: grandSales,
    sales_prev_quarter: salesPrev,
    sales_prev2_quarter: salesPrev2,
    dynamics_percent: salesPrev ? (grandSales / salesPrev) * 100 : null,
    dynamics_qty: grandSales - salesPrev,
    comment: null,
    next_quarter_plan: nextPlan,
    recommendations_text: "",
    matrix: [...zipDimRows(metalRows, ltsRows, wearRows), { metal_color: total, lts: total, wear_type: total, is_total: true }],
  };
}

export function formatValueWithTrend(formatted: string, trend?: string | null): string {
  if (!trend) return formatted;
  if (!formatted || formatted === "—") return trend;
  return `${formatted} ${trend}`;
}

export const DYNAMICS_HINT =
  "Динамика = факт этого квартала / факт прошлого. Рост — два квартала подряд больше предыдущего, Падение — меньше, Удержание — равно, Нестабильный — направление сменилось.";

export function formatDynamicsValue(value: number | null | undefined, trend?: string | null): string {
  if (value == null || Number.isNaN(Number(value))) return formatValueWithTrend("—", trend);
  const pct = Number(value) * 100;
  const formatted = `${pct.toLocaleString("ru-RU", { maximumFractionDigits: 0 })}% к пред.`;
  return formatValueWithTrend(formatted, trend);
}

export function trendClass(trend?: string | null): string {
  if (trend === "Рост") return "dyn-up";
  if (trend === "Падение") return "dyn-down";
  if (trend === "Нестабильный") return "dyn-unstable";
  if (trend === "Удержание") return "dyn-hold";
  return "";
}

export function isWorkTypeLabel(value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  return !/^[-—–]+$/.test(text);
}

export function uniqueWorkTypes(clients: { work_type_label?: string | null; work_type?: string | null }[]): string[] {
  return [
    ...new Set(
      clients
        .map((c) => c.work_type_label || c.work_type || "")
        .filter(isWorkTypeLabel),
    ),
  ].sort((a, b) => a.localeCompare(b, "ru"));
}

export function uniqueManagers(clients: { manager_name?: string | null }[]): string[] {
  return [...new Set(clients.map((c) => c.manager_name || "").filter(Boolean))].sort((a, b) => a.localeCompare(b, "ru"));
}
