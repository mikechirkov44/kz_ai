export type WorkTypeClient = {
  work_type?: string | null;
  work_type_label?: string | null;
};

export type DwellCell = { months_without_sales: number };

export type RecSeverity = { severity: string };

export type PlanClient = { counterparty: string; percent: number };

export type ChartSlice = { name: string; value: number; fill: string };

const WORK_COLORS: Record<string, string> = {
  hold: "#0f766e",
  growth: "#c4a574",
  decline: "#dc2626",
  other: "#9ca3af",
};

const WORK_LABELS: Record<string, string> = {
  hold: "Удержание",
  growth: "Рост",
  decline: "Падение",
  other: "Не задан",
};

export function workTypeChart(clients: WorkTypeClient[]): ChartSlice[] {
  const counts = { hold: 0, growth: 0, decline: 0, other: 0 };
  for (const client of clients) {
    const key = (client.work_type || "").trim().toLowerCase();
    if (key === "hold" || key === "growth" || key === "decline") counts[key] += 1;
    else counts.other += 1;
  }
  return (["hold", "growth", "decline", "other"] as const)
    .filter((key) => counts[key] > 0)
    .map((key) => ({ name: WORK_LABELS[key], value: counts[key], fill: WORK_COLORS[key] }));
}

export function dwellBucketChart(cells: DwellCell[], options?: { includeEmpty?: boolean }): ChartSlice[] {
  const counts = { fresh: 0, warm: 0, stale: 0, dead: 0 };
  for (const cell of cells) {
    const months = cell.months_without_sales;
    if (months <= 1) counts.fresh += 1;
    else if (months <= 3) counts.warm += 1;
    else if (months <= 6) counts.stale += 1;
    else counts.dead += 1;
  }
  const rows = [
    { name: "0–1 мес.", value: counts.fresh, fill: "#059669" },
    { name: "2–3", value: counts.warm, fill: "#d97706" },
    { name: "4–6", value: counts.stale, fill: "#ea580c" },
    { name: "7+", value: counts.dead, fill: "#dc2626" },
  ];
  return options?.includeEmpty ? rows : rows.filter((row) => row.value > 0);
}

export function recSeverityChart(items: RecSeverity[]): ChartSlice[] {
  const counts = { high: 0, medium: 0, low: 0 };
  for (const item of items) {
    const key = item.severity === "high" || item.severity === "medium" ? item.severity : "low";
    counts[key] += 1;
  }
  return [
    { name: "Срочно", value: counts.high, fill: "#dc2626" },
    { name: "Важно", value: counts.medium, fill: "#d97706" },
    { name: "На заметку", value: counts.low, fill: "#059669" },
  ].filter((row) => row.value > 0);
}

export function planPercentChart(clients: PlanClient[], limit = 12): { name: string; percent: number }[] {
  return [...clients]
    .filter((client) => Number(client.percent) < 100)
    .sort((a, b) => a.percent - b.percent)
    .slice(0, limit)
    .map((client) => ({
      name: shortLabel(client.counterparty, 22),
      percent: Number(client.percent) || 0,
    }));
}

export type SalesClient = {
  counterparty: string;
  manager_name?: string | null;
  sales_total?: number;
};

export type SalesBar = { name: string; sales: number };

export function topSalesByCounterparty(clients: SalesClient[], limit = 5): SalesBar[] {
  return [...clients]
    .map((client) => ({
      name: shortLabel(client.counterparty, 28),
      sales: Number(client.sales_total) || 0,
    }))
    .filter((row) => row.sales > 0)
    .sort((a, b) => b.sales - a.sales)
    .slice(0, limit);
}

export function topSalesByManager(clients: SalesClient[], limit = 5): SalesBar[] {
  const sums = new Map<string, number>();
  for (const client of clients) {
    const sales = Number(client.sales_total) || 0;
    if (sales <= 0) continue;
    const name = (client.manager_name || "").trim() || "Без менеджера";
    sums.set(name, (sums.get(name) || 0) + sales);
  }
  return [...sums.entries()]
    .map(([name, sales]) => ({ name: shortLabel(name, 28), sales }))
    .sort((a, b) => b.sales - a.sales)
    .slice(0, limit);
}

function shortLabel(value: string, max: number): string {
  const name = value.trim();
  if (name.length <= max) return name;
  return `${name.slice(0, Math.max(1, max - 1))}…`;
}

export function prettyArticle(article: string): string {
  const text = article.trim();
  if (/^\d+$/.test(text)) return String(Number(text));
  return text;
}

const MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

export type WeeklyWeek = {
  week_index: number;
  week_start: string;
  week_end: string;
  days: number;
  plan: number | string;
  fact: number | string;
  percent: number | string;
  is_current: boolean;
};

export type WeeklyBar = {
  name: string;
  label: string;
  plan: number;
  fact: number;
  percent: number;
  isCurrent: boolean;
};

function parseIsoParts(iso: string): { y: number; m: number; d: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (!match) return null;
  return { y: Number(match[1]), m: Number(match[2]), d: Number(match[3]) };
}

export function weekRangeLabel(startIso: string, endIso: string): string {
  const start = parseIsoParts(startIso);
  const end = parseIsoParts(endIso);
  if (!start || !end) return "";
  const sm = MONTHS_SHORT[start.m - 1] || "";
  const em = MONTHS_SHORT[end.m - 1] || "";
  if (start.m === end.m) return `${start.d}–${end.d} ${sm}`;
  return `${start.d} ${sm}–${end.d} ${em}`;
}

export function weeklyPlanChart(weeks: WeeklyWeek[]): WeeklyBar[] {
  return weeks.map((week) => ({
    name: `Н${week.week_index}`,
    label: weekRangeLabel(week.week_start, week.week_end),
    plan: Number(week.plan) || 0,
    fact: Number(week.fact) || 0,
    percent: Number(week.percent) || 0,
    isCurrent: Boolean(week.is_current),
  }));
}

export function currentWeeklyBar(rows: WeeklyBar[]): WeeklyBar | undefined {
  return rows.find((row) => row.isCurrent);
}
