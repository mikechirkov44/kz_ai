import { Fragment, useState } from "react";
import { api, downloadFile, formatMoney } from "../api";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";
import { MONTH_OPTIONS } from "../months";

type MatrixRow = {
  row_type?: string;
  counterparty?: string;
  dimension?: string;
  article?: string;
  name?: string;
  wear_type?: string;
  metal_color?: string;
  lts?: string;
  lts_days?: number;
  work_type?: string;
  work_type_percent?: number;
  proposal?: number;
  months: Record<
    string,
    {
      stock_begin: number;
      stock_end: number;
      sales: number;
      turnover_percent: number;
      realization?: number;
      return_qty?: number;
    }
  >;
};

export default function TurnoverPage() {
  const [view, setView] = useState("counterparty");
  const [yearFrom, setYearFrom] = useState(2023);
  const [monthFrom, setMonthFrom] = useState(1);
  const [yearTo, setYearTo] = useState(2023);
  const [monthTo, setMonthTo] = useState(3);
  const [months, setMonths] = useState<string[]>([]);
  const [rows, setRows] = useState<MatrixRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const sp = new URLSearchParams({
        view,
        year_from: String(yearFrom),
        month_from: String(monthFrom),
        year_to: String(yearTo),
        month_to: String(monthTo),
      });
      const data = await api<{ months: string[]; rows: MatrixRow[] }>(
        `/api/v1/reports/turnover-matrix?${sp}`,
      );
      setMonths(data.months);
      setRows(data.rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }

  const isMain = view === "main";

  return (
    <>
      <PageHeader
        title="Оборачиваемость"
        subtitle="Матрица по месяцам — как в Excel-примерах (5 срезов)"
        actions={
          <div className="toolbar">
            <button className="btn" onClick={load} disabled={loading}>
              {loading ? "Считаем…" : "Сформировать"}
            </button>
            <button
              className="btn secondary"
              onClick={() => {
                const sp = new URLSearchParams({
                  view,
                  year_from: String(yearFrom),
                  month_from: String(monthFrom),
                  year_to: String(yearTo),
                  month_to: String(monthTo),
                });
                downloadFile(`/api/v1/reports/turnover-matrix.xlsx?${sp}`, "turnover.xlsx").catch(
                  (err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"),
                );
              }}
            >
              Excel
            </button>
          </div>
        }
      />
      <div className="panel grid-3">
        <label className="field">
          <span>Срез (как в Excel)</span>
          <Select
            value={view}
            onChange={setView}
            options={[
              { value: "counterparty", label: "По контрагенту" },
              { value: "lts", label: "По ЖЦТ" },
              { value: "wear_type", label: "По типу ношения" },
              { value: "metal_color", label: "По цвету металла" },
              { value: "main", label: "Основной (SKU)" },
            ]}
          />
        </label>
        <label className="field">
          <span>С года / месяца</span>
          <div style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
            <input
              type="number"
              value={yearFrom}
              onChange={(e) => setYearFrom(Number(e.target.value))}
              style={{ flex: "1 1 55%" }}
            />
            <div style={{ flex: "1 1 45%" }}>
              <Select
                value={String(monthFrom)}
                onChange={(v) => setMonthFrom(Number(v))}
                options={MONTH_OPTIONS}
              />
            </div>
          </div>
        </label>
        <label className="field">
          <span>По год / месяц</span>
          <div style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
            <input
              type="number"
              value={yearTo}
              onChange={(e) => setYearTo(Number(e.target.value))}
              style={{ flex: "1 1 55%" }}
            />
            <div style={{ flex: "1 1 45%" }}>
              <Select
                value={String(monthTo)}
                onChange={(v) => setMonthTo(Number(v))}
                options={MONTH_OPTIONS}
              />
            </div>
          </div>
        </label>
      </div>
      {error && <div className="alert">{error}</div>}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="sticky">Контрагент / измерение</th>
              {isMain && <th>Артикул</th>}
              {isMain && <th>ЖЦТ</th>}
              {isMain && <th>Дней ЖЦТ</th>}
              {view === "counterparty" && <th>Тип работы</th>}
              {months.map((m) => (
                <th key={m} colSpan={isMain ? 4 : 3} style={{ textAlign: "center" }}>
                  {m}
                </th>
              ))}
              {view === "counterparty" && <th>Предложение</th>}
            </tr>
            <tr>
              <th className="sticky" />
              {isMain && <th />}
              {isMain && <th />}
              {isMain && <th />}
              {view === "counterparty" && <th />}
              {months.map((m) =>
                isMain ? (
                  <Fragment key={m}>
                    <th>Реал.</th>
                    <th>Возвр.</th>
                    <th>Прод.</th>
                    <th>Ост.</th>
                  </Fragment>
                ) : (
                  <Fragment key={m}>
                    <th>Ост.нач</th>
                    <th>Ост.кон</th>
                    <th>Прод.</th>
                  </Fragment>
                ),
              )}
              {view === "counterparty" && <th />}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={idx} style={r.row_type === "counterparty" ? { fontWeight: 600 } : undefined}>
                <td className="sticky">{r.dimension || r.counterparty || "—"}</td>
                {isMain && <td>{r.article || ""}</td>}
                {isMain && <td>{r.lts || ""}</td>}
                {isMain && <td>{r.lts_days ?? ""}</td>}
                {view === "counterparty" && <td>{r.work_type || ""}</td>}
                {months.map((m) => {
                  const cell = r.months?.[m] || {
                    stock_begin: 0,
                    stock_end: 0,
                    sales: 0,
                    realization: 0,
                    return_qty: 0,
                  };
                  if (isMain) {
                    return (
                      <Fragment key={m}>
                        <td>{formatMoney(cell.realization || 0)}</td>
                        <td>{formatMoney(cell.return_qty || 0)}</td>
                        <td>{formatMoney(cell.sales)}</td>
                        <td>{formatMoney(cell.stock_end)}</td>
                      </Fragment>
                    );
                  }
                  return (
                    <Fragment key={m}>
                      <td>{formatMoney(cell.stock_begin)}</td>
                      <td>{formatMoney(cell.stock_end)}</td>
                      <td>{formatMoney(cell.sales)}</td>
                    </Fragment>
                  );
                })}
                {view === "counterparty" && (
                  <td>{r.proposal != null ? formatMoney(r.proposal) : ""}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <p className="empty">Выберите период и нажмите «Сформировать». Нужны promo-клиенты и Excel продажи/остатки.</p>
        )}
        </div>
      </div>
    </>
  );
}
