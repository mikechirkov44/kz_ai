import { describe, expect, it } from "vitest";
import {
  formatTurnoverPct,
  groupKeysWithChildren,
  groupTurnoverRows,
  isEmptyMatrixRow,
  quarterTurnoverCell,
  totalTurnoverRow,
  turnoverToneClass,
  visibleTurnoverRows,
  type TurnoverMatrixRow,
} from "./turnoverMatrix";

function row(partial: Partial<TurnoverMatrixRow> & { months: TurnoverMatrixRow["months"] }): TurnoverMatrixRow {
  return partial as TurnoverMatrixRow;
}

const zero = { stock_begin: 0, stock_end: 0, sales: 0, turnover_percent: 0 };
const live = { stock_begin: 4, stock_end: 0, sales: 1, turnover_percent: 50 };

describe("turnoverMatrix", () => {
  it("formats turnover percent and tone", () => {
    expect(formatTurnoverPct(100)).toBe("100%");
    expect(formatTurnoverPct(0)).toBe("0%");
    expect(formatTurnoverPct(55.56)).toMatch(/55[,.]6%/);
    expect(turnoverToneClass(5)).toBe("turn-low");
    expect(turnoverToneClass(20)).toBe("turn-mid");
    expect(turnoverToneClass(40)).toBe("turn-ok");
  });

  it("detects empty rows including 1C movements", () => {
    expect(
      isEmptyMatrixRow(
        row({
          months: { "2026-07": { ...zero, realization: 0, return_qty: 0 } },
        }),
      ),
    ).toBe(true);
    expect(isEmptyMatrixRow(row({ months: { "2026-07": live } }))).toBe(false);
  });

  it("groups children under the counterparty parent", () => {
    const groups = groupTurnoverRows([
      row({ row_type: "counterparty", counterparty: "A", counterparty_id: "1", months: { "2026-07": live } }),
      row({ row_type: "dimension", dimension: "Актив", months: { "2026-07": live } }),
      row({ row_type: "dimension", dimension: "Вывод", months: { "2026-07": zero } }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].children.map((c) => c.dimension)).toEqual(["Актив", "Вывод"]);
  });

  it("hides empty children and all-zero groups", () => {
    const rows = [
      row({
        row_type: "counterparty",
        counterparty: "Empty",
        counterparty_id: "e",
        months: { "2026-07": zero },
      }),
      row({ row_type: "dimension", dimension: "Архив", months: { "2026-07": zero } }),
      row({
        row_type: "counterparty",
        counterparty: "Live",
        counterparty_id: "l",
        months: { "2026-07": live },
      }),
      row({ row_type: "dimension", dimension: "Актив", months: { "2026-07": live } }),
      row({ row_type: "dimension", dimension: "Вывод", months: { "2026-07": zero } }),
    ];
    const visible = visibleTurnoverRows(rows, { hideEmpty: true, collapsed: new Set() });
    expect(visible.map((r) => r.dimension || r.counterparty)).toEqual(["Live", "Актив"]);
  });

  it("collapses children but keeps the parent", () => {
    const rows = [
      row({
        row_type: "counterparty",
        counterparty: "Live",
        counterparty_id: "l",
        months: { "2026-07": live },
      }),
      row({ row_type: "dimension", dimension: "Актив", months: { "2026-07": live } }),
    ];
    const visible = visibleTurnoverRows(rows, { hideEmpty: true, collapsed: new Set(["l"]) });
    expect(visible.map((r) => r.counterparty)).toEqual(["Live"]);
    expect(groupKeysWithChildren(rows, true)).toEqual(["l"]);
  });

  it("totals only parent rows and recomputes turnover", () => {
    const rows = [
      row({
        row_type: "counterparty",
        counterparty: "A",
        months: { "2026-07": { stock_begin: 56, stock_end: 72, sales: 6, turnover_percent: 9.4 } },
      }),
      row({
        row_type: "dimension",
        dimension: "Актив",
        months: { "2026-07": { stock_begin: 20, stock_end: 30, sales: 2, turnover_percent: 8 } },
      }),
      row({
        row_type: "counterparty",
        counterparty: "B",
        months: { "2026-07": { stock_begin: 10, stock_end: 10, sales: 4, turnover_percent: 40 } },
      }),
    ];
    const total = totalTurnoverRow(rows, ["2026-07"], { hideEmpty: false });
    expect(total.counterparty).toBe("Итого");
    expect(total.months["2026-07"].stock_begin).toBe(66);
    expect(total.months["2026-07"].stock_end).toBe(82);
    expect(total.months["2026-07"].sales).toBe(10);
    expect(total.months["2026-07"].stock_avg).toBe(74);
    expect(total.months["2026-07"].turnover_percent).toBeCloseTo((10 / 74) * 100);
  });

  it("quarter cell uses monthly average stocks", () => {
    const item = row({
      counterparty: "Гранат",
      months: {
        "2026-07": { stock_begin: 56, stock_end: 72, sales: 6, turnover_percent: 9.4 },
        "2026-08": { stock_begin: 72, stock_end: 58, sales: 13, turnover_percent: 20 },
        "2026-09": { stock_begin: 58, stock_end: 54, sales: 4, turnover_percent: 7.1 },
      },
    });
    const q = quarterTurnoverCell(item, ["2026-07", "2026-08", "2026-09"]);
    expect(q.stock_avg).toBeCloseTo(61.666, 2);
    expect(q.sales).toBe(23);
  });

  it("keeps flat counterparty rows when they have qty", () => {
    const rows = [
      row({ counterparty: "Z", months: { "2026-07": zero } }),
      row({ counterparty: "L", months: { "2026-07": live } }),
    ];
    expect(visibleTurnoverRows(rows, { hideEmpty: true, collapsed: new Set() }).map((r) => r.counterparty)).toEqual([
      "L",
    ]);
  });
});
