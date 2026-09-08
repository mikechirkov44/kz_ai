import { parseIsoDate } from "./months";

export type DateRange = { from: string; to: string };

const PREFIX = "period:";

export function readStoredPeriod(key: string, fallback: DateRange): DateRange {
  if (typeof localStorage === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(`${PREFIX}${key}`);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as { from?: unknown; to?: unknown };
    const from = typeof parsed.from === "string" ? parsed.from : "";
    const to = typeof parsed.to === "string" ? parsed.to : "";
    if (parseIsoDate(from) && parseIsoDate(to)) return { from, to };
  } catch {
    /* ignore broken storage */
  }
  return fallback;
}

export function writeStoredPeriod(key: string, range: DateRange): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(`${PREFIX}${key}`, JSON.stringify(range));
}
