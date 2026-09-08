export type TurnoverMonthCell = {
  stock_begin: number;
  stock_end: number;
  stock_avg?: number;
  sales: number;
  turnover_percent: number;
  realization?: number;
  return_qty?: number;
};

export type TurnoverMatrixRow = {
  row_type?: string;
  counterparty?: string;
  counterparty_id?: string;
  dimension?: string;
  article?: string;
  name?: string;
  wear_type?: string;
  metal_color?: string;
  lts?: string;
  work_type?: string;
  work_type_percent?: number;
  months: Record<string, TurnoverMonthCell>;
};

export type TurnoverGroup = {
  parent: TurnoverMatrixRow;
  children: TurnoverMatrixRow[];
};

const CHILD_TYPES = new Set(["dimension", "sku"]);

export function formatTurnoverPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "0%";
  return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
}

export function turnoverToneClass(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "turn-low";
  if (value < 10) return "turn-low";
  if (value < 30) return "turn-mid";
  return "turn-ok";
}

export function isEmptyMonthCell(cell?: TurnoverMonthCell): boolean {
  if (!cell) return true;
  return (
    !Number(cell.stock_begin) &&
    !Number(cell.stock_end) &&
    !Number(cell.sales) &&
    !Number(cell.realization) &&
    !Number(cell.return_qty)
  );
}

export function isEmptyMatrixRow(row: TurnoverMatrixRow): boolean {
  const cells = Object.values(row.months || {});
  if (!cells.length) return true;
  return cells.every(isEmptyMonthCell);
}

export function groupKey(row: TurnoverMatrixRow): string {
  return row.counterparty_id || row.counterparty || "";
}

export function groupTurnoverRows(rows: TurnoverMatrixRow[]): TurnoverGroup[] {
  const groups: TurnoverGroup[] = [];
  for (const row of rows) {
    if (row.row_type === "counterparty") {
      groups.push({ parent: row, children: [] });
      continue;
    }
    if (CHILD_TYPES.has(row.row_type || "")) {
      const last = groups[groups.length - 1];
      if (last) last.children.push(row);
      else groups.push({ parent: row, children: [] });
      continue;
    }
    groups.push({ parent: row, children: [] });
  }
  return groups;
}

export function visibleTurnoverRows(
  rows: TurnoverMatrixRow[],
  opts: { hideEmpty: boolean; collapsed: ReadonlySet<string> },
): TurnoverMatrixRow[] {
  const out: TurnoverMatrixRow[] = [];
  for (const group of groupTurnoverRows(rows)) {
    const children = opts.hideEmpty ? group.children.filter((row) => !isEmptyMatrixRow(row)) : group.children;
    if (opts.hideEmpty && isEmptyMatrixRow(group.parent) && children.length === 0) continue;
    out.push(group.parent);
    if (children.length && !opts.collapsed.has(groupKey(group.parent))) {
      out.push(...children);
    }
  }
  return out;
}

export function groupKeysWithChildren(rows: TurnoverMatrixRow[], hideEmpty: boolean): string[] {
  return groupTurnoverRows(rows)
    .filter((group) => {
      const children = hideEmpty ? group.children.filter((row) => !isEmptyMatrixRow(row)) : group.children;
      return children.length > 0;
    })
    .map((group) => groupKey(group.parent))
    .filter(Boolean);
}
