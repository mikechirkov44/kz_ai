import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import QuarterlyTzSheet from "./QuarterlyTzSheet";
import type { SummaryClient } from "./QuarterlyMatrix";

afterEach(cleanup);

const client: SummaryClient = {
  counterparty_id: "c1",
  counterparty: "ИП Garant.S",
  plan: 50,
  sales_prev_quarter: 80,
  sales_prev2_quarter: 70,
  dynamics_percent: 43,
  comment: null,
  next_quarter_plan: 34,
  recommendations_text: "Подсортировать кольца.",
  recommendations: [{ message: "Подсортировать кольца.", title: "Довезите кольца" }],
  matrix: [
    {
      wear_type: {
        dimension: "Кольцо",
        avg_stock: 5,
        sales_total: 4,
        quarter_turnover_percent: 80,
        avg_month_turnover_percent: 26.7,
      },
      recommendations: [{ message: "Довезите кольца" }],
      recommendations_text: "Довезите кольца",
    },
    {
      is_total: true,
      wear_type: {
        dimension: "Итого",
        avg_stock: 5,
        sales_total: 4,
        quarter_turnover_percent: 80,
        avg_month_turnover_percent: 26.7,
      },
      recommendations: [{ message: "Верните залежалый товар." }],
      recommendations_text: "Верните залежалый товар.",
    },
  ],
};

describe("QuarterlyTzSheet recommendations", () => {
  it("hides recommendations while the client is collapsed", () => {
    render(<QuarterlyTzSheet year={2026} quarter={3} clients={[client]} />);
    expect(screen.queryByText("Подсортировать кольца.")).toBeNull();
    expect(screen.queryByText("Довезите кольца")).toBeNull();
    expect(screen.queryByText("Верните залежалый товар.")).toBeNull();
  });

  it("shows per-row recommendations after expand", () => {
    render(<QuarterlyTzSheet year={2026} quarter={3} clients={[client]} />);
    fireEvent.click(screen.getByRole("button", { name: "Развернуть все" }));
    expect(screen.getByText("Довезите кольца")).toBeTruthy();
    expect(screen.getByText("Верните залежалый товар.")).toBeTruthy();
    expect(screen.queryByText("Подсортировать кольца.")).toBeNull();
  });
});
