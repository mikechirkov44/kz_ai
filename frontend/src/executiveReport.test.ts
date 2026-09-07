import { describe, expect, it } from "vitest";
import { buildExecutiveReport, detailNumber } from "./executiveReport";
import type { Recommendation } from "./recommendations";

const sample: Recommendation[] = [
  {
    type: "illiquid",
    severity: "high",
    action: "return",
    message: "Вернуть X",
    title: "Верните 8 шт. X",
    counterparty: "Alpha",
    score: 80,
    details: { suggest_qty: "8", months_without_sales: 9 },
  },
  {
    type: "pattern",
    severity: "info",
    action: "restock",
    message: "Довезите",
    title: "Довезите 4 шт.",
    counterparty: "Beta",
    score: 40,
    details: { suggest_qty: "4" },
  },
  {
    type: "price_arbitrage",
    severity: "high",
    action: "reprice",
    message: "Цена",
    title: "Снизить цену · Кольцо",
    counterparty: "Alpha",
    score: 90,
    details: { gap_percent: "22.5", wear_type: "Кольцо" },
  },
  {
    type: "price_arbitrage",
    severity: "medium",
    action: "reprice",
    message: "Цена",
    title: "Снизить цену · Серьги",
    counterparty: "Gamma",
    score: 70,
    details: { gap_percent: "10", wear_type: "Серьги" },
  },
];

describe("executiveReport", () => {
  it("parses detail numbers", () => {
    expect(detailNumber({ gap_percent: "22,5" }, "gap_percent")).toBe(22.5);
    expect(detailNumber({ months_without_sales: 9 }, "months_without_sales")).toBe(9);
    expect(detailNumber({}, "gap_percent")).toBeNull();
  });

  it("builds a full digest with empty actions kept", () => {
    const report = buildExecutiveReport(sample);
    expect(report.total).toBe(4);
    expect(report.clients).toBe(3);
    expect(report.severity).toEqual({ high: 2, medium: 1, info: 1 });
    expect(report.actions).toEqual({ return: 1, restock: 1, transfer: 0, reprice: 2 });
    expect(report.blocks).toHaveLength(4);
    const price = report.blocks.find((block) => block.action === "reprice");
    expect(price?.facts.some((fact) => fact.label === "Макс. разрыв" && fact.value === "22.5%")).toBe(true);
    const transfer = report.blocks.find((block) => block.action === "transfer");
    expect(transfer?.count).toBe(0);
    expect(report.focus[0]?.counterparty).toBe("Alpha");
    expect(report.focus[0]?.signals).toBe(2);
  });
});
