import { describe, expect, it } from "vitest";
import {
  compactRecNumber,
  filterRecommendations,
  groupRecommendations,
  llmStatusLabel,
  recActionLabel,
  recSeverityLabel,
  recTypeLabel,
  recWhyChips,
  splitRecNumbers,
  topRecommendations,
  type Recommendation,
} from "./recommendations";

const sample: Recommendation[] = [
  { type: "illiquid", severity: "high", message: "A", action: "return", score: 40, title: "Вернуть X" },
  { type: "pattern", severity: "info", message: "B", action: "restock", score: 90, title: "Подсортировать" },
  { type: "price_arbitrage", severity: "high", message: "C", action: "reprice", score: 70 },
];

describe("recommendations", () => {
  it("maps labels", () => {
    expect(recTypeLabel("illiquid")).toBe("Залежалый товар");
    expect(recTypeLabel("mix")).toBe("Перекос");
    expect(recActionLabel("return")).toBe("Вернуть");
    expect(recSeverityLabel("high")).toBe("Срочно");
    expect(llmStatusLabel("ok")).toBe("Обогащено моделью");
    expect(llmStatusLabel("off")).toBe("По правилам сервиса");
  });

  it("filters and ranks", () => {
    expect(filterRecommendations(sample, "restock")).toHaveLength(1);
    expect(filterRecommendations(sample, "all")).toHaveLength(3);
    expect(topRecommendations(sample, 2).map((row) => row.action)).toEqual(["restock", "reprice"]);
  });

  it("builds why chips", () => {
    expect(
      recWhyChips({
        type: "illiquid",
        severity: "high",
        message: "x",
        action: "return",
        details: { months_without_sales: 7, avg_turnover: "4.50", stock_qty: "10", suggest_qty: "10" },
      }),
    ).toEqual(["верните 10 шт.", "7 мес. без продаж", "об-ть 4.50%", "остаток 10"]);
  });

  it("groups by client and keeps top score first", () => {
    const groups = groupRecommendations([
      { type: "illiquid", severity: "high", message: "A", counterparty: "Beta", score: 20 },
      { type: "pattern", severity: "info", message: "B", counterparty: "Alpha", score: 90 },
      { type: "mix", severity: "high", message: "C", counterparty: "Alpha", score: 40 },
    ]);
    expect(groups.map((row) => row.counterparty)).toEqual(["Alpha", "Beta"]);
    expect(groups[0].items.map((row) => row.score)).toEqual([90, 40]);
  });

  it("compacts and splits numbers in recommendation text", () => {
    expect(compactRecNumber("43098.281333333333333333333333")).toBe("43 098");
    expect(compactRecNumber("62%")).toBe("62%");
    expect(compactRecNumber("4")).toBe("4");
    const parts = splitRecNumbers("не выше 43098.281333 тенге, разрыв 62%.");
    expect(parts.filter((p) => p.number).map((p) => p.value)).toEqual(["43 098", "62%"]);
    expect(splitRecNumbers("артикул Б2450-120БР").some((p) => p.number)).toBe(false);
    expect(splitRecNumbers("артикул К/261-0320").some((p) => p.number)).toBe(false);
  });
});
