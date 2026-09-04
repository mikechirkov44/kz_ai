export const DOC_TYPE_LABEL: Record<string, string> = {
  realization: "Реализация",
  return: "Возврат",
  order: "Заказ",
  production: "Производство",
};

export function docTypeLabel(type?: string | null): string {
  if (!type) return "";
  return DOC_TYPE_LABEL[type] || type;
}

export function linesQuantity(lines: { quantity?: number | null }[] | undefined): number {
  return (lines || []).reduce((sum, line) => sum + Number(line.quantity || 0), 0);
}

export function documentTotalQuantity(
  totalQuantity?: number | null,
  lines?: { quantity?: number | null }[],
): number {
  const fromLines = linesQuantity(lines);
  return fromLines || Number(totalQuantity || 0);
}
