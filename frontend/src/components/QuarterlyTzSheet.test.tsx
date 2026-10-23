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
  it("paints the metric header row with the same block colors", () => {
    const { container } = render(<QuarterlyTzSheet year={2026} quarter={3} clients={[client]} />);
    const heads = [...(container.querySelector("thead tr:nth-child(2)")?.querySelectorAll("th") || [])].filter(
      (th) => !th.classList.contains("tz-matrix-fix"),
    );
    expect(heads.slice(0, 5).every((th) => th.classList.contains("blk-metal"))).toBe(true);
    expect(heads.slice(5, 10).every((th) => th.classList.contains("blk-lts"))).toBe(true);
    expect(heads.slice(10, 15).every((th) => th.classList.contains("blk-wear"))).toBe(true);
    expect(heads.filter((_, idx) => idx % 5 === 0).every((th) => !th.classList.contains("num"))).toBe(true);
    expect(heads.filter((_, idx) => idx % 5 !== 0).every((th) => th.classList.contains("num"))).toBe(true);
  });

  it("hides recommendations while the client is collapsed", () => {
    render(<QuarterlyTzSheet year={2026} quarter={3} clients={[client]} />);
    expect(screen.queryByText("Подсортировать кольца.")).toBeNull();
    expect(screen.queryByText("Довезите кольца")).toBeNull();
    expect(screen.queryByText("Верните залежалый товар.")).toBeNull();
  });

  it("shows a dash for catalog wear types the client never had", () => {
    render(
      <QuarterlyTzSheet
        year={2026}
        quarter={3}
        clients={[
          {
            ...client,
            matrix: [
              {
                wear_type: {
                  dimension: "Кольцо",
                  avg_stock: 5,
                  sales_total: 4,
                  quarter_turnover_percent: 80,
                  avg_month_turnover_percent: 26.7,
                },
              },
              {
                wear_type: {
                  dimension: "Браслет",
                  avg_stock: null,
                  sales_total: null,
                  quarter_turnover_percent: null,
                  avg_month_turnover_percent: null,
                  is_empty: true,
                },
              },
              client.matrix[1],
            ],
          },
        ]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Развернуть все" }));
    expect(screen.getAllByText("Браслет").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("-").length).toBeGreaterThanOrEqual(4);
  });

  it("shows per-row recommendations after expand", () => {
    render(<QuarterlyTzSheet year={2026} quarter={3} clients={[client]} />);
    fireEvent.click(screen.getByRole("button", { name: "Развернуть все" }));
    expect(screen.getByText("Довезите кольца")).toBeTruthy();
    expect(screen.getByText("Верните залежалый товар.")).toBeTruthy();
    expect(screen.queryByText("Подсортировать кольца.")).toBeNull();
  });
});
