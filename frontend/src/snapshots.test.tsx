import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import EmptyState from "./components/EmptyState";
import { ExcelLabel } from "./components/ExcelIcon";
import TableSkeleton from "./components/TableSkeleton";
import DataTable from "./components/DataTable";
import DwellHeatmap from "./components/DwellHeatmap";
import FilePicker from "./components/FilePicker";
import PageHeader from "./components/PageHeader";
import PeriodPicker from "./components/PeriodPicker";
import QuarterlyMatrix from "./components/QuarterlyMatrix";
import QuarterlyResultsSheet from "./components/QuarterlyResultsSheet";
import QuarterlyTzSheet from "./components/QuarterlyTzSheet";
import SourceSelect from "./components/SourceSelect";
import AiBriefing from "./components/AiBriefing";
import CbrRates from "./components/CbrRates";
import ExecutiveReport from "./components/ExecutiveReport";
import RecommendationCard from "./components/RecommendationCard";
import UploadErrorsModal from "./components/UploadErrorsModal";
import UploadFileModal from "./components/UploadFileModal";
import Pager from "./components/Pager";
import HelpPage from "./pages/HelpPage";
import SettingsPage from "./pages/SettingsPage";

describe("snapshots", () => {
  it("EmptyState", () => {
    const { container } = render(
      <MemoryRouter>
        <EmptyState
          title="Нет продаж за период"
          hint="Загрузите Excel продаж."
          action={{ to: "/uploads", label: "Загрузить продажи" }}
        />
      </MemoryRouter>,
    );
    expect(container).toMatchSnapshot();
  });

  it("TableSkeleton", () => {
    const { container } = render(<TableSkeleton rows={2} cols={3} />);
    expect(container).toMatchSnapshot();
  });

  it("DataTable empty", () => {
    const { container } = render(
      <MemoryRouter>
        <DataTable
          rows={[]}
          rowKey={() => "x"}
          empty="Нет продаж за период"
          emptyHint="Загрузите Excel."
          emptyAction={{ to: "/uploads", label: "Загрузить продажи" }}
          columns={[{ key: "name", title: "Клиент" }]}
        />
      </MemoryRouter>,
    );
    expect(container).toMatchSnapshot();
  });

  it("DataTable numbers", () => {
    const { container } = render(
      <MemoryRouter>
        <DataTable
          rows={[{ name: "ИП Garant.S", qty: 12, amount: 43098 }]}
          rowKey={(row) => row.name}
          columns={[
            { key: "name", title: "Клиент", sticky: true },
            { key: "qty", title: "Шт", align: "right", width: 80 },
            { key: "amount", title: "Сумма", align: "right", width: 120 },
          ]}
        />
      </MemoryRouter>,
    );
    expect(container).toMatchSnapshot();
  });

  it("PageHeader", () => {
    const { container } = render(
      <MemoryRouter>
        <PageHeader title="Дашборд" subtitle="Сводка" />
      </MemoryRouter>,
    );
    expect(container).toMatchSnapshot();
  });

  it("SettingsPage", () => {
    const { container } = render(
      <MemoryRouter>
        <SettingsPage />
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
        counterparties={[{ id: "c1", name: "ТОО Alpha", source_id: "asil" }]}
        articles={["000001797"]}
        articleNames={{ "000001797": "Кольцо золото" }}
        cells={[
          {
            counterparty_id: "c1",
            counterparty: "ТОО Alpha",
            article: "000001797",
            months_without_sales: 7,
            stock_qty: 3,
          },
        ]}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("QuarterlyMatrix", () => {
    const { container } = render(
      <MemoryRouter>
      <QuarterlyMatrix
        labels={{
          plan: "План отгрузки на 3 квартал",
          sales: "итого продажи 3 кв",
          turnover: "Об-ть 3 кв",
          avg_turnover: "Ср. об-ть за 3 кв",
          sales_prev: "итого продажи 2 кв.",
          sales_prev2: "итого продажи 1 кв.",
          dynamics: "Динамика 3 кв. / 2 кв. (шт)",
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
      />
      </MemoryRouter>,
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
          dynamics: "Динамика 3 кв. / 2 кв. (шт)",
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
            dynamics_qty: -46,
            comment: "Участвует в повышенной мотивации",
            next_quarter_plan: 34,
            recommendations_text: "Подсортировать кольца.",
            recommendations: [
              { message: "Подсортировать кольца.", title: "Довезите кольца" },
              { message: "Верните залежалый товар." },
            ],
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
        onSaveComment={async () => undefined}
        onShowHistory={() => undefined}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("QuarterlyResultsSheet", () => {
    const { container } = render(
      <QuarterlyResultsSheet
        year={2026}
        quarter={3}
        labels={{
          plan: "План отгрузок на 3 квартал",
          shipment_fact: "Факт отгрузок 3 квартал",
          shipment_percent: "% выполнения",
          shipment_prev: "Факт отгрузок 2 квартал",
          shipment_prev2: "Факт отгрузок 1 квартал",
          shipment_dynamics: "Динамика отгрузок",
          sales: "Продажи 3 кв.",
          sales_prev: "Продажи 2 кв.",
          sales_prev2: "Продажи 1 кв.",
          sales_dynamics: "Динамика продаж",
        }}
        clients={[
          {
            counterparty_id: "c1",
            counterparty: "ИП Garant.S",
            manager_name: "Иванов",
            work_type_label: "Удержание",
            work_type_percent: 0,
            plan: 0,
            shipment_fact: 40,
            shipment_percent: 0,
            shipment_prev_quarter: 50,
            shipment_prev2_quarter: 30,
            shipment_dynamics_percent: 80,
            sales_total: 34,
            sales_prev_quarter: 80,
            sales_prev2_quarter: 70,
            dynamics_percent: 42.5,
            comment: "Участвует в повышенной мотивации",
          },
        ]}
        onSaveComment={async () => undefined}
        onShowHistory={() => undefined}
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

  it("AiBriefing", () => {
    const { container } = render(
      <AiBriefing summary="Вижу 2 сигнала. Первым делом: ТОО Alpha — Вернуть X1." llmStatus="off" count={2} />,
    );
    expect(container).toMatchSnapshot();
  });

  it("AiBriefing enriched", () => {
    const { container } = render(
      <AiBriefing
        summary="Вижу 2 сигнала. Первым делом: ТОО Alpha — Вернуть X1."
        llmStatus="ok"
        count={2}
        items={[
          {
            type: "illiquid",
            severity: "high",
            action: "return",
            title: "Вернуть X1",
            score: 82,
            counterparty: "ТОО Alpha",
            message: "Вернуть X1",
            llm_comment: "Предложите обмен на ходовую связку.",
          },
        ]}
        onOpenReport={() => undefined}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("ExecutiveReport", () => {
    const { container } = render(
      <ExecutiveReport
        summary="Начните с возврата у ТОО Alpha."
        llmReport={{ headline: "Сначала возврат", situation: "Начните с возврата у ТОО Alpha.", notes: { return: "Верните залежалое." } }}
        items={[
          {
            type: "illiquid",
            severity: "high",
            action: "return",
            title: "Вернуть X1",
            score: 82,
            counterparty: "ТОО Alpha",
            message: "Вернуть X1",
            details: { suggest_qty: "8", months_without_sales: 7 },
          },
        ]}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("RecommendationCard", () => {
    const { container } = render(
      <RecommendationCard
        item={{
          type: "illiquid",
          severity: "high",
          action: "return",
          title: "Вернуть X1",
          score: 82,
          counterparty: "ТОО Alpha",
          article: "X1",
          message: "Вернуть или обменять артикул X1.",
          details: { months_without_sales: 7, avg_turnover: "4.50" },
          llm_comment: "Предложите обмен на ходовую связку.",
        }}
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

  it("UploadErrorsModal", () => {
    const { container } = render(
      <UploadErrorsModal
        open
        processedRows={10}
        errors={[{ row: 4, field: "article", message: "Нет в справочнике" }]}
        onClose={() => undefined}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("UploadFileModal", () => {
    const { container } = render(
      <UploadFileModal
        open
        title="template_sales.xlsx"
        subtitle="Продажи · Успех"
        preview={{
          file_name: "template_sales.xlsx",
          upload_type: "sales",
          status: "success",
          has_file: true,
          has_errors: false,
          columns: ["Головной контрагент", "Артикул", "Количество"],
          rows: [{ "Головной контрагент": "ИП Garant.S", Артикул: "IM-001", Количество: 2 }],
          total_rows: 1,
          shown_rows: 1,
        }}
        onClose={() => undefined}
        onDownloadFile={() => undefined}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("UploadFileModal errors tab", () => {
    const { container } = render(
      <UploadFileModal
        open
        title="sales.xlsx"
        subtitle="Продажи · Частично"
        initialTab="errors"
        preview={{
          file_name: "sales.xlsx",
          upload_type: "sales",
          status: "partial",
          has_file: true,
          has_errors: true,
          errors: [{ row: 4, field: "article", message: "Нет в справочнике" }],
          columns: ["Головной контрагент", "Артикул"],
          rows: [{ "Головной контрагент": "ИП Garant.S", Артикул: "IM-001" }],
          total_rows: 1,
          shown_rows: 1,
        }}
        onClose={() => undefined}
        onDownloadFile={() => undefined}
      />,
    );
    expect(container).toMatchSnapshot();
  });

  it("Pager", () => {
    const { container } = render(<Pager page={1} total={216} onChange={() => undefined} />);
    expect(container).toMatchSnapshot();
  });

  it("ExcelLabel", () => {
    const { container } = render(<ExcelLabel>Excel</ExcelLabel>);
    expect(container).toMatchSnapshot();
  });
});
