export const MONTH_OPTIONS = [
  { value: "1", label: "Январь" },
  { value: "2", label: "Февраль" },
  { value: "3", label: "Март" },
  { value: "4", label: "Апрель" },
  { value: "5", label: "Май" },
  { value: "6", label: "Июнь" },
  { value: "7", label: "Июль" },
  { value: "8", label: "Август" },
  { value: "9", label: "Сентябрь" },
  { value: "10", label: "Октябрь" },
  { value: "11", label: "Ноябрь" },
  { value: "12", label: "Декабрь" },
];

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function isoToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function monthRange(year: number, month: number): { from: string; to: string } {
  const last = new Date(year, month, 0).getDate();
  return { from: `${year}-${pad(month)}-01`, to: `${year}-${pad(month)}-${pad(last)}` };
}

export function quarterRange(year: number, quarter: number): { from: string; to: string } {
  const startMonth = (quarter - 1) * 3 + 1;
  return { from: monthRange(year, startMonth).from, to: monthRange(year, startMonth + 2).to };
}

export function yearRange(year: number): { from: string; to: string } {
  return { from: `${year}-01-01`, to: `${year}-12-31` };
}

export type PeriodGrain = "month" | "quarter" | "year";
export type PeriodMode = "range" | "month" | "quarter" | "month-range";

export function parseIsoDate(value: string): { year: number; month: number; day: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) return null;
  return { year: Number(m[1]), month: Number(m[2]), day: Number(m[3]) };
}

export function formatRuDate(iso: string): string {
  const p = parseIsoDate(iso);
  if (!p) return "";
  return `${pad(p.day)}.${pad(p.month)}.${p.year}`;
}

export function parseRuDate(text: string): string | null {
  const m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(text.trim());
  if (!m) return null;
  const day = Number(m[1]);
  const month = Number(m[2]);
  const year = Number(m[3]);
  if (month < 1 || month > 12 || day < 1) return null;
  const last = new Date(year, month, 0).getDate();
  if (day > last) return null;
  return `${year}-${pad(month)}-${pad(day)}`;
}

export function ymIndex(year: number, month: number): number {
  return year * 12 + month;
}

function swapIfNeeded(from: string, to: string): { from: string; to: string } {
  return from <= to ? { from, to } : { from: to, to: from };
}

export function snapPeriod(from: string, to: string, mode: PeriodMode): { from: string; to: string } {
  const ordered = swapIfNeeded(from, to);
  const a = parseIsoDate(ordered.from);
  const b = parseIsoDate(ordered.to);
  if (!a || !b) return ordered;
  if (mode === "month") return monthRange(a.year, a.month);
  if (mode === "quarter") return quarterRange(a.year, Math.floor((a.month - 1) / 3) + 1);
  if (mode === "month-range") {
    return { from: monthRange(a.year, a.month).from, to: monthRange(b.year, b.month).to };
  }
  return ordered;
}

export function monthClickPeriod(
  mode: PeriodMode,
  year: number,
  month: number,
  draftFrom: string,
  pickingEnd: boolean,
): { from: string; to: string; pickingEnd: boolean } {
  const clicked = monthRange(year, month);
  if (mode === "month") return { from: clicked.from, to: clicked.to, pickingEnd: false };
  if (mode === "quarter") {
    const q = quarterRange(year, Math.floor((month - 1) / 3) + 1);
    return { from: q.from, to: q.to, pickingEnd: false };
  }
  if (!pickingEnd) return { from: clicked.from, to: clicked.to, pickingEnd: true };
  const start = parseIsoDate(draftFrom);
  if (!start) return { from: clicked.from, to: clicked.to, pickingEnd: false };
  const startIdx = ymIndex(start.year, start.month);
  const endIdx = ymIndex(year, month);
  if (startIdx <= endIdx) {
    return { from: monthRange(start.year, start.month).from, to: clicked.to, pickingEnd: false };
  }
  return { from: clicked.from, to: monthRange(start.year, start.month).to, pickingEnd: false };
}

export function currentMonthRange(now = new Date()): { from: string; to: string } {
  return monthRange(now.getFullYear(), now.getMonth() + 1);
}

export function previousMonthRange(now = new Date()): { from: string; to: string } {
  const d = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return monthRange(d.getFullYear(), d.getMonth() + 1);
}

export function currentQuarterRange(now = new Date()): { from: string; to: string } {
  return quarterRange(now.getFullYear(), Math.floor(now.getMonth() / 3) + 1);
}

export function previousQuarterRange(now = new Date()): { from: string; to: string } {
  const q = Math.floor(now.getMonth() / 3);
  if (q === 0) return quarterRange(now.getFullYear() - 1, 4);
  return quarterRange(now.getFullYear(), q);
}

export function previousYearRange(now = new Date()): { from: string; to: string } {
  return yearRange(now.getFullYear() - 1);
}

export function defaultPeriodForMode(mode: PeriodMode, now = new Date()): { from: string; to: string } {
  if (mode === "month") return currentMonthRange(now);
  return currentQuarterRange(now);
}

export function standardPeriodOptions(now = new Date()): { id: string; label: string; from: string; to: string }[] {
  const y = now.getFullYear();
  return [
    { id: "this-month", label: "Этот месяц", ...currentMonthRange(now) },
    { id: "prev-month", label: "Прошлый месяц", ...previousMonthRange(now) },
    { id: "this-quarter", label: "Этот квартал", ...currentQuarterRange(now) },
    { id: "prev-quarter", label: "Прошлый квартал", ...previousQuarterRange(now) },
    { id: "this-year", label: "Этот год", ...yearRange(y) },
    { id: "prev-year", label: "Прошлый год", ...previousYearRange(now) },
  ];
}

export function yearMonthFromIso(from: string): { year: number; month: number } {
  const p = parseIsoDate(from);
  if (!p) return { year: new Date().getFullYear(), month: 1 };
  return { year: p.year, month: p.month };
}

export function yearQuarterFromIso(from: string): { year: number; quarter: number } {
  const p = parseIsoDate(from);
  if (!p) return { year: new Date().getFullYear(), quarter: 1 };
  return { year: p.year, quarter: Math.floor((p.month - 1) / 3) + 1 };
}
