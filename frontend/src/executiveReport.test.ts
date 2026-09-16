import { describe, expect, it } from "vitest";
import {
  buildExecutiveReport,
  buildPlaybook,
  detailNumber,
  isExitLts,
  itemPlanPercent,
  playbookWhy,
} from "./executiveReport";
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
    details: { suggest_qty: "8", months_without_sales: 9, plan_percent: "12.0", wear_type: "Кольцо" },
  },
  {
    type: "pattern",
    severity: "info",
    action: "restock",
    message: "Довезите",
    title: "Довезите 4 шт.",
    counterparty: "Beta",
    score: 40,
    details: { suggest_qty: "4", wear_type: "Серьги", plan_percent: "88" },
  },
  {
    type: "price_arbitrage",
    severity: "high",
    action: "reprice",
    message: "Цена",
    title: "Снизить цену · Кольцо",
    counterparty: "Alpha",
    score: 90,
    details: { gap_percent: "22.5", wear_type: "Кольцо", plan_percent: "12.0", articles: [{ article: "R-1", gap_percent: "31", client_avg_price: "120000", shipment_avg_price: "174000" }] },
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
    expect(itemPlanPercent(sample[0])).toBe(12);
    expect(isExitLts({ lts: "Вывод" })).toBe(true);
    expect(isExitLts({ lts: "Актив" })).toBe(false);
  });

  it("builds a full digest with empty actions kept", () => {
    const report = buildExecutiveReport(sample);
    expect(report.total).toBe(4);
    expect(report.clients).toBe(3);
    expect(report.behindPlan).toBe(1);
    expect(report.planKnown).toBe(2);
    expect(report.severity).toEqual({ high: 2, medium: 1, info: 1 });
    expect(report.actions).toEqual({ return: 1, restock: 1, transfer: 0, reprice: 2 });
    expect(report.blocks).toHaveLength(4);
    const price = report.blocks.find((block) => block.action === "reprice");
    expect(price?.facts.some((fact) => fact.label === "Макс. разрыв" && fact.value === "22.5%")).toBe(true);
    expect(price?.facts.some((fact) => fact.label === "Артикулов" && fact.value === "1")).toBe(true);
    expect(price?.top[0]).toMatchObject({ counterparty: "Alpha", title: "R-1", clientAvg: 120000, shipmentAvg: 174000 });
    const transfer = report.blocks.find((block) => block.action === "transfer");
    expect(transfer?.count).toBe(0);
    expect(report.focus[0]?.counterparty).toBe("Alpha");
    expect(report.focus[0]?.behind).toBe(true);
    expect(report.focus[0]?.signals).toBe(2);
    expect(report.wear.map((row) => row.wear)).toEqual(["Кольцо", "Серьги"]);
    expect(report.playbook[0]).toMatchObject({ counterparty: "Alpha", action: "reprice" });
  });

  it("puts mix and exit LTS on return, ranks top by score, and lists transfer destinations", () => {
    const rows: Recommendation[] = [
      {
        type: "illiquid",
        severity: "medium",
        action: "return",
        message: "Верните много",
        title: "Верните 20 шт. BIG",
        counterparty: "OnPlan",
        score: 40,
        details: { suggest_qty: "20", months_without_sales: 7, plan_percent: "90", wear_type: "Браслет" },
      },
      {
        type: "mix",
        severity: "high",
        action: "return",
        message: "Перекос",
        title: "Верните 3 шт. и довезите ходовое",
        counterparty: "Lagging",
        score: 95,
        details: {
          suggest_qty: "3",
          months_without_sales: 10,
          plan_percent: "18",
          wear_type: "Кольцо",
          lts: "Вывод",
        },
      },
      {
        type: "transfer",
        severity: "high",
        action: "transfer",
        message: "Переложите",
        title: "Переложите 5 шт.",
        counterparty: "Donor",
        score: 70,
        details: { suggest_qty: "5", to_counterparty: "Need", wear_type: "Серьги", months_without_sales: 8 },
      },
    ];
    const report = buildExecutiveReport(rows);
    const ret = report.blocks.find((block) => block.action === "return");
    expect(ret?.facts.some((fact) => fact.label === "Перекос" && fact.value === "1")).toBe(true);
    expect(ret?.facts.some((fact) => fact.label === "ЖЦТ Вывод" && fact.value === "1")).toBe(true);
    expect(ret?.top[0]?.tag).toBe("Перекос");
    expect(ret?.top[0]?.counterparty).toBe("Lagging");
    const transfer = report.blocks.find((block) => block.action === "transfer");
    expect(transfer?.facts.some((fact) => fact.label === "Куда везти" && fact.value === "1")).toBe(true);
    expect(transfer?.top[0]?.counterparty).toBe("Donor → Need");
    expect(report.focus[0]?.counterparty).toBe("Lagging");
    expect(report.focus.map((row) => row.counterparty)).toEqual(["Lagging", "Donor", "OnPlan"]);
    expect(report.exitLts).toBe(1);
    expect(report.mixCount).toBe(1);
    expect(playbookWhy(rows[1])).toContain("перекос ассортимента");
    expect(playbookWhy(rows[1])).toContain("ЖЦТ Вывод");
    expect(buildPlaybook(rows).map((step) => `${step.counterparty}:${step.action}`)).toEqual([
      "Lagging:return",
      "Donor:transfer",
      "OnPlan:return",
    ]);
  });
});
