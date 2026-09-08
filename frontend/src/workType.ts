const WORK_TYPE_LABELS: Record<string, string> = {
  hold: "Удержание",
  growth: "Рост",
  decline: "Падение",
  удержание: "Удержание",
  рост: "Рост",
  прирост: "Рост",
  падение: "Падение",
};

export function workTypeLabel(raw?: string | null): string {
  const value = (raw || "").trim();
  if (!value) return "—";
  return WORK_TYPE_LABELS[value.toLowerCase()] || value;
}

export function formatWorkTypePercent(value?: number | null): string {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const amount = Number(value);
  const body = Number.isInteger(amount)
    ? String(amount)
    : amount.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  return `${body}%`;
}
