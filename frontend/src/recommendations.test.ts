import { describe, expect, it } from "vitest";
import {
  filterRecommendations,
  llmStatusLabel,
  recActionLabel,
  recSeverityLabel,
  recTypeLabel,
  recWhyChips,
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
        details: { months_without_sales: 7, avg_turnover: "4.50", stock_qty: "10" },
      }),
    ).toEqual(["7 мес. без продаж", "об-ть 4.50%", "остаток 10"]);
  });
});
