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

export function dwellBucketChart(cells: DwellCell[]): ChartSlice[] {
  const counts = { fresh: 0, warm: 0, stale: 0, dead: 0 };
  for (const cell of cells) {
    const months = cell.months_without_sales;
    if (months <= 1) counts.fresh += 1;
    else if (months <= 3) counts.warm += 1;
    else if (months <= 6) counts.stale += 1;
    else counts.dead += 1;
  }
  return [
    { name: "0–1 мес.", value: counts.fresh, fill: "#059669" },
    { name: "2–3", value: counts.warm, fill: "#d97706" },
    { name: "4–6", value: counts.stale, fill: "#ea580c" },
    { name: "7+", value: counts.dead, fill: "#dc2626" },
  ].filter((row) => row.value > 0);
}

export function recSeverityChart(items: RecSeverity[]): ChartSlice[] {
  const counts = { high: 0, medium: 0, low: 0 };
  for (const item of items) {
    const key = item.severity === "high" || item.severity === "medium" ? item.severity : "low";
    counts[key] += 1;
  }
  return [
    { name: "Высокий", value: counts.high, fill: "#dc2626" },
    { name: "Средний", value: counts.medium, fill: "#d97706" },
    { name: "Низкий", value: counts.low, fill: "#059669" },
  ].filter((row) => row.value > 0);
}

export function planPercentChart(clients: PlanClient[], limit = 12): { name: string; percent: number }[] {
  return [...clients]
    .sort((a, b) => a.percent - b.percent)
    .slice(0, limit)
    .map((client) => ({
      name: client.counterparty.length > 22 ? `${client.counterparty.slice(0, 20)}…` : client.counterparty,
      percent: Number(client.percent) || 0,
    }));
}

export function prettyArticle(article: string): string {
  const text = article.trim();
  if (/^\d+$/.test(text)) return String(Number(text));
  return text;
}
