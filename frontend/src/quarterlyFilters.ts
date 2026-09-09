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

export function formatValueWithTrend(formatted: string, trend?: string | null): string {
  if (!trend) return formatted;
  if (!formatted || formatted === "—") return trend;
  return `${formatted} ${trend}`;
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
