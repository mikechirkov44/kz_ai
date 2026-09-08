export type HeatmapCounterparty = {
  id: string;
  name: string;
  source_id?: string;
};

export type HeatmapCounterpartyInput = string | HeatmapCounterparty;

export type HeatmapCell = {
  counterparty?: string;
  counterparty_id?: string;
  article: string;
  months_without_sales: number;
  stock_qty: number;
};

export function normalizeHeatmapCounterparties(raw: HeatmapCounterpartyInput[]): HeatmapCounterparty[] {
  return raw.map((item, idx) => {
    if (typeof item === "string") {
      return { id: item || `row-${idx}`, name: item };
    }
    return {
      id: item.id || item.name || `row-${idx}`,
      name: item.name,
      source_id: item.source_id,
    };
  });
}

export function heatmapCellKey(counterpartyId: string, article: string): string {
  return `${counterpartyId}|${article}`;
}

export function heatmapRowLabel(
  row: HeatmapCounterparty,
  duplicateNames: Set<string>,
  sourceLabel?: (sourceId: string) => string,
): string {
  if (duplicateNames.has(row.name) && row.source_id) {
    const source = sourceLabel ? sourceLabel(row.source_id) : row.source_id;
    return `${row.name} · ${source}`;
  }
  return row.name;
}

export function heatmapDuplicateNames(rows: HeatmapCounterparty[]): Set<string> {
  const counts = new Map<string, number>();
  for (const row of rows) {
    counts.set(row.name, (counts.get(row.name) || 0) + 1);
  }
  return new Set([...counts.entries()].filter(([, count]) => count > 1).map(([name]) => name));
}
