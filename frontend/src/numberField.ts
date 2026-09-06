export function stepNumber(
  value: string,
  delta: number,
  opts: { min?: number; integer?: boolean } = {},
): string {
  const current = Number(String(value).replace(",", ".").replace(/\s/g, ""));
  const base = Number.isFinite(current) ? current : 0;
  let next = base + delta;
  if (opts.min != null) next = Math.max(opts.min, next);
  if (opts.integer) next = Math.round(next);
  return String(next);
}

export function appendDigit(value: string, digit: string, integer = false): string {
  if (digit === "⌫") {
    return value.slice(0, -1);
  }
  if (digit === "," || digit === ".") {
    if (integer || value.includes(".") || value.includes(",")) return value;
    return value ? `${value}.` : "0.";
  }
  if (!/^\d$/.test(digit)) return value;
  if (value === "0") return digit;
  return `${value}${digit}`;
}
