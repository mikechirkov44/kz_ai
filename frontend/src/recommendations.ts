export type RecAction = "return" | "restock" | "reprice";

export type Recommendation = {
  type: string;
  severity: string;
  counterparty?: string;
  article?: string;
  message: string;
  llm_comment?: string | null;
  title?: string;
  action?: string;
  score?: number;
  details?: Record<string, unknown>;
};

export const REC_ACTION_TABS: { id: "all" | RecAction; label: string }[] = [
  { id: "all", label: "Все" },
  { id: "return", label: "Вернуть" },
  { id: "restock", label: "Подсортировать" },
  { id: "reprice", label: "Цена" },
];

const TYPE_LABELS: Record<string, string> = {
  illiquid: "Залежалый товар",
  pattern: "Подсортировка",
  price_arbitrage: "Цена отгрузки",
  mix: "Перекос",
};

const ACTION_LABELS: Record<string, string> = {
  return: "Вернуть",
  restock: "Подсортировать",
  reprice: "Снизить цену",
};

const SEVERITY_LABELS: Record<string, string> = {
  high: "Срочно",
  medium: "Важно",
  info: "На заметку",
  low: "На заметку",
};

export function recTypeLabel(type: string): string {
  return TYPE_LABELS[type] || type;
}

export function recActionLabel(action: string): string {
  return ACTION_LABELS[action] || action;
}

export function recSeverityLabel(severity: string): string {
  return SEVERITY_LABELS[severity] || severity;
}

export function llmStatusLabel(status: string): string {
  if (status === "ok") return "Обогащено моделью";
  if (status === "error") return "Правила сервиса · модель недоступна";
  return "По правилам сервиса";
}

export function filterRecommendations(items: Recommendation[], action: string): Recommendation[] {
  if (action === "all") return items;
  return items.filter((item) => item.action === action);
}

export function topRecommendations(items: Recommendation[], limit: number): Recommendation[] {
  return [...items]
    .sort((a, b) => (b.score || 0) - (a.score || 0))
    .slice(0, limit);
}

export function recWhyChips(item: Recommendation): string[] {
  const details = item.details || {};
  const chips: string[] = [];
  const months = details.months_without_sales;
  if (typeof months === "number" && months > 0) chips.push(`${months} мес. без продаж`);
  const turn = details.avg_turnover;
  if (typeof turn === "string" && turn) chips.push(`об-ть ${turn}%`);
  const sales = details.sales || details.strong_sales;
  if (typeof sales === "string" && sales) chips.push(`продажи ${sales}`);
  const stock = details.stock_qty || details.weak_stock;
  if (typeof stock === "string" && stock) chips.push(`остаток ${stock}`);
  return chips.slice(0, 4);
}
