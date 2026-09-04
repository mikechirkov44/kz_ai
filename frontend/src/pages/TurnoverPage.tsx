import { Fragment, useState } from "react";
import { api, downloadFile, formatMoney } from "../api";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import Select from "../components/Select";
import { quarterRange, yearMonthFromIso } from "../months";

type MatrixRow = {
  row_type?: string;
  counterparty?: string;
  dimension?: string;
  article?: string;
  name?: string;
  wear_type?: string;
  metal_color?: string;
  lts?: string;
  work_type?: string;
  work_type_percent?: number;
  months: Record<
    string,
    {
      stock_begin: number;
      stock_end: number;
      stock_avg?: number;
      sales: number;
      turnover_percent: number;
      realization?: number;
      return_qty?: number;
    }
  >;
};

export default function TurnoverPage() {
  const [view, setView] = useState("counterparty");
  const initial = quarterRange(2023, 1);
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const start = yearMonthFromIso(from);
  const end = yearMonthFromIso(to);
  const [months, setMonths] = useState<string[]>([]);
  const [rows, setRows] = useState<MatrixRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [avgStock, setAvgStock] = useState(false);

  function periodParams(): URLSearchParams {
    return new URLSearchParams({
      view,
      year_from: String(start.year),
      month_from: String(start.month),
      year_to: String(end.year),
      month_to: String(end.month),
    });
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api<{ months: string[]; rows: MatrixRow[] }>(
        `/api/v1/reports/turnover-matrix?${periodParams()}`,
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
        subtitle="Продажи, остатки и оборачиваемость по месяцам"
        actions={
          <div className="toolbar">
            <button className="btn" onClick={load} disabled={loading}>
              {loading ? "Считаем…" : "Сформировать"}
            </button>
            <button
              className="btn secondary"
              onClick={() => {
                downloadFile(`/api/v1/reports/turnover-matrix.xlsx?${periodParams()}`, "turnover.xlsx").catch(
                  (err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"),
                );
              }}
            >
              Excel
            </button>
          </div>
        }
      />
      <div className="panel filters-bar grid-2">
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
        <PeriodPicker
          from={from}
          to={to}
          mode="month-range"
          onChange={(nextFrom, nextTo) => {
            setFrom(nextFrom);
            setTo(nextTo);
          }}
        />
        {!isMain && (
          <label className="toggle" style={{ alignSelf: "end", marginBottom: 8 }}>
            <input type="checkbox" checked={avgStock} onChange={(e) => setAvgStock(e.target.checked)} />
            Средние остатки (вместо нач./кон.)
          </label>
        )}
      </div>
      {error && <div className="alert">{error}</div>}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="sticky">Контрагент / измерение</th>
              {isMain && <th>Артикул</th>}
              {isMain && <th>Тип изделия</th>}
              {isMain && <th>Цвет металла</th>}
              {isMain && <th>ЖЦТ</th>}
              {isMain && <th>Тип работы</th>}
              {isMain && <th>% типа работы</th>}
              {months.map((m) => (
                <th key={m} colSpan={isMain ? 5 : avgStock ? 2 : 3} style={{ textAlign: "center" }}>
                  {m}
                </th>
              ))}
            </tr>
            <tr>
              <th className="sticky" />
              {isMain && <th />}
              {isMain && <th />}
              {isMain && <th />}
              {isMain && <th />}
              {isMain && <th />}
              {isMain && <th />}
              {months.map((m) =>
                isMain ? (
                  <Fragment key={m}>
                    <th>Ост.нач</th>
                    <th>Реал.</th>
                    <th>Возвр.</th>
                    <th>Ост.кон</th>
                    <th>Прод.</th>
                  </Fragment>
                ) : avgStock ? (
                  <Fragment key={m}>
                    <th>Ср.ост</th>
                    <th>Прод.</th>
                  </Fragment>
                ) : (
                  <Fragment key={m}>
                    <th>Ост.нач</th>
                    <th>Ост.кон</th>
                    <th>Прод.</th>
                  </Fragment>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={idx} style={r.row_type === "counterparty" ? { fontWeight: 600 } : undefined}>
                <td className="sticky">{r.dimension || r.counterparty || "—"}</td>
                {isMain && <td>{r.article || r.name || ""}</td>}
                {isMain && <td>{r.wear_type || ""}</td>}
                {isMain && <td>{r.metal_color || ""}</td>}
                {isMain && <td>{r.lts || ""}</td>}
                {isMain && <td>{r.work_type || ""}</td>}
                {isMain && <td>{r.work_type_percent ?? ""}</td>}
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
                        <td>{formatMoney(cell.stock_begin)}</td>
                        <td>{formatMoney(cell.realization || 0)}</td>
                        <td>{formatMoney(cell.return_qty || 0)}</td>
                        <td>{formatMoney(cell.stock_end)}</td>
                        <td>{formatMoney(cell.sales)}</td>
                      </Fragment>
                    );
                  }
                  if (avgStock) {
                    const avg =
                      cell.stock_avg != null
                        ? cell.stock_avg
                        : (Number(cell.stock_begin) + Number(cell.stock_end)) / 2;
                    return (
                      <Fragment key={m}>
                        <td>{formatMoney(avg)}</td>
                        <td>{formatMoney(cell.sales)}</td>
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
