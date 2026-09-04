import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import CbrRates from "./components/CbrRates";
import DwellHeatmap from "./components/DwellHeatmap";
import FilePicker from "./components/FilePicker";
import PageHeader from "./components/PageHeader";
import PeriodPicker from "./components/PeriodPicker";
import QuarterlyMatrix from "./components/QuarterlyMatrix";
import QuarterlyTzSheet from "./components/QuarterlyTzSheet";
import SourceSelect from "./components/SourceSelect";
import HelpPage from "./pages/HelpPage";

describe("snapshots", () => {
  it("PageHeader", () => {
    const { container } = render(
      <MemoryRouter>
        <PageHeader title="Дашборд" subtitle="Сводка" />
      </MemoryRouter>,
    );
    expect(container).toMatchSnapshot();
  });

  it("HelpPage", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/help"]}>
        <HelpPage />
      </MemoryRouter>,
    );
    expect(container).toMatchSnapshot();
  });

  it("PeriodPicker", () => {
    const { container } = render(
      <PeriodPicker
        from="2023-01-01"
        to="2023-03-31"
        mode="quarter"
        minYear={2023}
        maxYear={2023}
        onChange={() => undefined}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("FilePicker", () => {
    const { container } = render(<FilePicker file={null} onChange={() => undefined} />);
    expect(container).toMatchSnapshot();
  });

  it("DwellHeatmap", () => {
    const { container } = render(
      <DwellHeatmap
        counterparties={["ТОО Alpha"]}
        articles={["000001797"]}
        articleNames={{ "000001797": "Кольцо золото" }}
        cells={[{ counterparty: "ТОО Alpha", article: "000001797", months_without_sales: 7, stock_qty: 3 }]}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("QuarterlyMatrix", () => {
    const { container } = render(
      <QuarterlyMatrix
        labels={{
          plan: "План отгрузки на 3 квартал",
          sales: "итого продажи 3 кв",
          turnover: "Об-ть 3 кв",
          avg_turnover: "Ср. об-ть за 3 кв",
          sales_prev: "итого продажи 2 кв.",
          sales_prev2: "итого продажи 1 кв.",
          dynamics: "Динамика 3 кв. / 2 кв.",
          next_plan: "План работы на 4 кв (шт)",
        }}
        clients={[
          {
            counterparty_id: "c1",
            counterparty: "ИП Garant.S",
            work_type_label: "Удержание",
            work_type_percent: 0,
            plan: 50,
            sales_prev_quarter: 80,
            sales_prev2_quarter: 70,
            dynamics_percent: 43,
            comment: "Участвует в повышенной мотивации",
            next_quarter_plan: 34,
            recommendations_text: "Подсортировать кольца Актив Ядро в красном золоте.",
            matrix: [
              {
                metal_color: {
                  dimension: "Красное 585",
                  avg_stock: 10,
                  sales_total: 8,
                  quarter_turnover_percent: 80,
                  avg_month_turnover_percent: 26.7,
                },
                lts: {
                  dimension: "Актив",
                  avg_stock: 12,
                  sales_total: 9,
                  quarter_turnover_percent: 75,
                  avg_month_turnover_percent: 25,
                },
                wear_type: {
                  dimension: "Кольцо",
                  avg_stock: 5,
                  sales_total: 4,
                  quarter_turnover_percent: 80,
                  avg_month_turnover_percent: 26.7,
                },
              },
              {
                is_total: true,
                metal_color: {
                  dimension: "Итого",
                  avg_stock: 10,
                  sales_total: 34,
                  quarter_turnover_percent: 340,
                  avg_month_turnover_percent: 113.3,
                },
                lts: {
                  dimension: "Итого",
                  avg_stock: 10,
                  sales_total: 34,
                  quarter_turnover_percent: 340,
                  avg_month_turnover_percent: 113.3,
                },
                wear_type: {
                  dimension: "Итого",
                  avg_stock: 10,
                  sales_total: 34,
                  quarter_turnover_percent: 340,
                  avg_month_turnover_percent: 113.3,
                },
              },
            ],
          },
        ]}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("QuarterlyTzSheet", () => {
    const { container } = render(
      <QuarterlyTzSheet
        year={2026}
        quarter={3}
        labels={{
          plan: "План отгрузки на 3 квартал",
          sales: "итого продажи 3 кв",
          turnover: "Об-ть 3 кв",
          avg_turnover: "Ср. об-ть за 3 кв",
          sales_prev: "итого продажи 2 кв.",
          sales_prev2: "итого продажи 1 кв.",
          dynamics: "Динамика 3 кв. / 2 кв.",
          next_plan: "План работы на 4 кв (шт)",
        }}
        clients={[
          {
            counterparty_id: "c1",
            counterparty: "ИП Garant.S",
            work_type_label: "Удержание",
            plan: 50,
            sales_prev_quarter: 80,
            sales_prev2_quarter: 70,
            dynamics_percent: 43,
            comment: "Участвует в повышенной мотивации",
            next_quarter_plan: 34,
            recommendations_text: "Подсортировать кольца.",
            matrix: [
              {
                metal_color: {
                  dimension: "Красное 585",
                  avg_stock: 10,
                  sales_total: 8,
                  quarter_turnover_percent: 80,
                  avg_month_turnover_percent: 26.7,
                },
                lts: {
                  dimension: "Актив",
                  avg_stock: 12,
                  sales_total: 9,
                  quarter_turnover_percent: 75,
                  avg_month_turnover_percent: 25,
                },
                wear_type: {
                  dimension: "Кольцо",
                  avg_stock: 5,
                  sales_total: 4,
                  quarter_turnover_percent: 80,
                  avg_month_turnover_percent: 26.7,
                },
              },
              {
                is_total: true,
                metal_color: {
                  dimension: "Итого",
                  avg_stock: 10,
                  sales_total: 34,
                  quarter_turnover_percent: 340,
                  avg_month_turnover_percent: 113.3,
                },
                lts: {
                  dimension: "Итого",
                  avg_stock: 10,
                  sales_total: 34,
                  quarter_turnover_percent: 340,
                  avg_month_turnover_percent: 113.3,
                },
                wear_type: {
                  dimension: "Итого",
                  avg_stock: 10,
                  sales_total: 34,
                  quarter_turnover_percent: 340,
                  avg_month_turnover_percent: 113.3,
                },
              },
            ],
          },
        ]}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("SourceSelect", () => {
    const { container } = render(
      <SourceSelect
        value=""
        onChange={() => undefined}
        sources={[
          { source_id: "base_1", label: "Основная", enabled: true },
          { source_id: "base_2", label: "Филиал", enabled: true },
        ]}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("CbrRates", () => {
    const { container } = render(
      <CbrRates
        data={{
          as_of: "2026-09-04",
          status: "ok",
          source: "cbr",
          items: [
            {
              code: "USD",
              name: "Доллар США",
              rate: 86.89,
              change_percent: -0.13,
              history: [
                { date: "2026-09-02", rate: 86.5 },
                { date: "2026-09-03", rate: 87.0 },
                { date: "2026-09-04", rate: 86.89 },
              ],
            },
            {
              code: "EUR",
              name: "Евро",
              rate: 100.6,
              change_percent: 0.23,
              history: [
                { date: "2026-09-03", rate: 100.37 },
                { date: "2026-09-04", rate: 100.6 },
              ],
            },
            {
              code: "KZT",
              name: "Тенге",
              rate: 0.1852,
              change_percent: -0.11,
              history: [
                { date: "2026-09-03", rate: 0.185 },
                { date: "2026-09-04", rate: 0.1852 },
              ],
            },
          ],
        }}
      />,
    );
    expect(container).toMatchSnapshot();
  });
});
