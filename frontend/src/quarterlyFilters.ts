import type { SummaryClient } from "./components/QuarterlyMatrix";

export type QuarterlyTab = "progress" | "summary" | "plan";

export const QUARTERLY_TABS: { id: QuarterlyTab; label: string }[] = [
  { id: "progress", label: "Промежуточные" },
  { id: "summary", label: "Итог" },
  { id: "plan", label: "План" },
];

export function isQuarterlyTab(value: string): value is QuarterlyTab {
  return QUARTERLY_TABS.some((tab) => tab.id === value);
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

export function isWorkTypeLabel(value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  return !/^[-—–]+$/.test(text);
}

export function uniqueWorkTypes(clients: SummaryClient[]): string[] {
  return [
    ...new Set(
      clients
        .map((c) => c.work_type_label || c.work_type || "")
        .filter(isWorkTypeLabel),
    ),
  ].sort((a, b) => a.localeCompare(b, "ru"));
}

export function uniqueManagers(clients: SummaryClient[]): string[] {
  return [...new Set(clients.map((c) => c.manager_name || "").filter(Boolean))].sort((a, b) => a.localeCompare(b, "ru"));
}
