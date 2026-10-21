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

export function isTurnoverChildRow(row: TurnoverMatrixRow): boolean {
  return row.row_type === "dimension" || row.row_type === "sku";
}

export function monthAvgStock(cell?: TurnoverMonthCell): number {
  if (!cell) return 0;
  if (cell.stock_avg != null && !Number.isNaN(Number(cell.stock_avg))) return Number(cell.stock_avg);
  return (Number(cell.stock_begin) + Number(cell.stock_end)) / 2;
}

export function turnoverFromAvg(sales: number, avgStock: number): number {
  if (!avgStock) return 0;
  return (sales / avgStock) * 100;
}

export function emptyMonthCell(): TurnoverMonthCell {
  return { stock_begin: 0, stock_end: 0, stock_avg: 0, sales: 0, realization: 0, return_qty: 0, turnover_percent: 0 };
}

export function quarterTurnoverCell(row: TurnoverMatrixRow, months: string[]): TurnoverMonthCell {
  const avgs: number[] = [];
  let sales = 0;
  let begin = 0;
  let end = 0;
  let realization = 0;
  let returnQty = 0;
  for (const month of months) {
    const cell = row.months?.[month];
    if (!cell) {
      avgs.push(0);
      continue;
    }
    avgs.push(monthAvgStock(cell));
    sales += Number(cell.sales) || 0;
    begin += Number(cell.stock_begin) || 0;
    end += Number(cell.stock_end) || 0;
    realization += Number(cell.realization) || 0;
    returnQty += Number(cell.return_qty) || 0;
  }
  const avg = avgs.length ? avgs.reduce((sum, value) => sum + value, 0) / Math.max(avgs.length, 3) : 0;
  return {
    stock_begin: begin,
    stock_end: end,
    stock_avg: avg,
    sales,
    realization,
    return_qty: returnQty,
    turnover_percent: turnoverFromAvg(sales, avg),
  };
}

export function totalTurnoverRow(
  rows: TurnoverMatrixRow[],
  months: string[],
  opts: { hideEmpty: boolean } = { hideEmpty: false },
): TurnoverMatrixRow {
  const parents = groupTurnoverRows(rows)
    .map((group) => group.parent)
    .filter((parent) => !(opts.hideEmpty && isEmptyMatrixRow(parent)));
  const cells: Record<string, TurnoverMonthCell> = {};
  for (const month of months) {
    let begin = 0;
    let end = 0;
    let sales = 0;
    let realization = 0;
    let returnQty = 0;
    for (const parent of parents) {
      const cell = parent.months?.[month];
      if (!cell) continue;
      begin += Number(cell.stock_begin) || 0;
      end += Number(cell.stock_end) || 0;
      sales += Number(cell.sales) || 0;
      realization += Number(cell.realization) || 0;
      returnQty += Number(cell.return_qty) || 0;
    }
    const avg = (begin + end) / 2;
    cells[month] = {
      stock_begin: begin,
      stock_end: end,
      stock_avg: avg,
      sales,
      realization,
      return_qty: returnQty,
      turnover_percent: turnoverFromAvg(sales, avg),
    };
  }
  return {
    row_type: "total",
    dimension: "Итого",
    counterparty: "Итого",
    months: cells,
  };
}
