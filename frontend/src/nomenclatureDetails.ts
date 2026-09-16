export type DetailRow = {
  label: string;
  value?: string | number | boolean | null;
  always?: boolean;
};

export function formatDetailValue(value?: string | number | boolean | null): string {
  if (typeof value === "boolean") return value ? "да" : "нет";
  if (value == null) return "—";
  const text = String(value).trim();
  return text || "—";
}

export function visibleDetailRows(rows: DetailRow[]): { label: string; text: string }[] {
  return rows
    .map((row) => ({ label: row.label, text: formatDetailValue(row.value), always: Boolean(row.always) }))
    .filter((row) => row.always || row.text !== "—");
}
