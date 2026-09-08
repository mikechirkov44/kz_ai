import { Fragment, useMemo, useState } from "react";
import { api, downloadFile, formatMoney } from "../api";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import Select from "../components/Select";
import TableSkeleton from "../components/TableSkeleton";
import { currentQuarterRange, yearMonthFromIso } from "../months";
import {
  groupKey,
  groupKeysWithChildren,
  formatTurnoverPct,
  turnoverToneClass,
  type TurnoverMatrixRow,
  visibleTurnoverRows,
} from "../turnoverMatrix";
import { useHorizontalOverflow } from "../useHorizontalOverflow";
import { useStoredPeriod } from "../useStoredPeriod";

export default function TurnoverPage() {
  const [view, setView] = useState("counterparty");
  const { from, to, setPeriod } = useStoredPeriod("turnover", currentQuarterRange());
  const start = yearMonthFromIso(from);
  const end = yearMonthFromIso(to);
  const [months, setMonths] = useState<string[]>([]);
  const [rows, setRows] = useState<TurnoverMatrixRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [avgStock, setAvgStock] = useState(false);
  const [hideEmpty, setHideEmpty] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());

  function periodParams(forExport = false): URLSearchParams {
    const sp = new URLSearchParams({
      view,
      year_from: String(start.year),
      month_from: String(start.month),
      year_to: String(end.year),
      month_to: String(end.month),
    });
    if (forExport && hideEmpty) sp.set("hide_empty", "true");
    return sp;
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api<{ months: string[]; rows: TurnoverMatrixRow[] }>(
        `/api/v1/reports/turnover-matrix?${periodParams()}`,
      );
      setMonths(data.months);
      setRows(data.rows);
      setCollapsed(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }

  const { ref: overflowRef, overflow } = useHorizontalOverflow([
    months,
    rows,
    view,
    avgStock,
    hideEmpty,
    collapsed,
    loading,
  ]);
  const isMain = view === "main";
  const visible = useMemo(
    () => visibleTurnoverRows(rows, { hideEmpty, collapsed }),
    [rows, hideEmpty, collapsed],
  );
  const foldKeys = useMemo(() => groupKeysWithChildren(rows, hideEmpty), [rows, hideEmpty]);
  const foldSet = useMemo(() => new Set(foldKeys), [foldKeys]);
  const canGroup = foldKeys.length > 0;

  function toggleGroup(key: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <>
      <PageHeader title="Оборачиваемость" subtitle="Продажи, остатки и оборачиваемость по месяцам" />
      <div className="panel filters-bar">
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
            setPeriod(nextFrom, nextTo);
          }}
        />
        {!isMain && (
          <label className="toggle" style={{ alignSelf: "end", marginBottom: 8 }}>
            <input type="checkbox" checked={avgStock} onChange={(e) => setAvgStock(e.target.checked)} />
            Средние остатки (вместо нач./кон.)
          </label>
        )}
        <label className="toggle" style={{ alignSelf: "end", marginBottom: 8 }}>
          <input type="checkbox" checked={hideEmpty} onChange={(e) => setHideEmpty(e.target.checked)} />
          Скрыть пустые строки
        </label>
        <div className="filters-actions">
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Считаем…" : "Показать"}
          </button>
          <button
            className="btn secondary"
            type="button"
            onClick={() => {
              downloadFile(`/api/v1/reports/turnover-matrix.xlsx?${periodParams(true)}`, "turnover.xlsx").catch(
                (err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"),
              );
            }}
          >
            Excel
          </button>
        </div>
      </div>
      {error && <div className="alert">{error}</div>}
      <div className="panel" style={{ padding: 16, overflow: "hidden" }}>
        {canGroup && !!visible.length && !loading && (
          <div className="toolbar" style={{ marginBottom: 10, gap: 8 }}>
            <button className="btn secondary sm" type="button" onClick={() => setCollapsed(new Set(foldKeys))}>
              Свернуть все
            </button>
            <button className="btn secondary sm" type="button" onClick={() => setCollapsed(new Set())}>
              Развернуть все
            </button>
          </div>
        )}
        {overflow && !!visible.length && !loading && <p className="wide-table-hint">Листайте таблицу вправо →</p>}
        {loading ? (
          <TableSkeleton rows={8} cols={6} />
        ) : !rows.length ? (
          <EmptyState
            title="Нет данных за период"
            hint="Выберите период и нажмите «Показать». Нужны акционные клиенты и Excel продаж/остатков."
            action={{ to: "/uploads", label: "Загрузить продажи" }}
          />
        ) : !visible.length ? (
          <EmptyState
            title="Все строки пустые"
            hint="Снимите «Скрыть пустые строки», чтобы увидеть нули."
          />
        ) : (
          <div className="table-wrap" ref={overflowRef} style={{ margin: 0 }}>
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
                    <th key={m} colSpan={isMain ? 6 : avgStock ? 3 : 4} style={{ textAlign: "center" }}>
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
                        <th>Об-ть %</th>
                      </Fragment>
                    ) : avgStock ? (
                      <Fragment key={m}>
                        <th>Ср.ост</th>
                        <th>Прод.</th>
                        <th>Об-ть %</th>
                      </Fragment>
                    ) : (
                      <Fragment key={m}>
                        <th>Ост.нач</th>
                        <th>Ост.кон</th>
                        <th>Прод.</th>
                        <th>Об-ть %</th>
                      </Fragment>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {visible.map((r, idx) => {
                  const key = groupKey(r);
                  const isChild = r.row_type === "dimension" || r.row_type === "sku";
                  const foldable = !isChild && foldSet.has(key);
                  const open = foldable && !collapsed.has(key);
                  return (
                    <tr
                      key={`${key}-${r.row_type || "row"}-${r.dimension || r.article || idx}`}
                      className={isChild ? "turn-child" : undefined}
                      style={r.row_type === "counterparty" || foldable ? { fontWeight: 600 } : undefined}
                    >
                      <td className="sticky">
                        {foldable ? (
                          <button
                            type="button"
                            className="turn-group-toggle"
                            onClick={() => toggleGroup(key)}
                            aria-expanded={open}
                          >
                            <span className="turn-group-caret">{open ? "▾" : "▸"}</span>
                            {r.dimension || r.counterparty || "—"}
                          </button>
                        ) : (
                          r.dimension || r.counterparty || "—"
                        )}
                      </td>
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
                          turnover_percent: 0,
                        };
                        if (isMain) {
                          return (
                            <Fragment key={m}>
                              <td>{formatMoney(cell.stock_begin)}</td>
                              <td>{formatMoney(cell.realization || 0)}</td>
                              <td>{formatMoney(cell.return_qty || 0)}</td>
                              <td>{formatMoney(cell.stock_end)}</td>
                              <td>{formatMoney(cell.sales)}</td>
                              <td className={`num ${turnoverToneClass(cell.turnover_percent)}`}>
                                {formatTurnoverPct(cell.turnover_percent)}
                              </td>
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
                              <td className={`num ${turnoverToneClass(cell.turnover_percent)}`}>
                                {formatTurnoverPct(cell.turnover_percent)}
                              </td>
                            </Fragment>
                          );
                        }
                        return (
                          <Fragment key={m}>
                            <td>{formatMoney(cell.stock_begin)}</td>
                            <td>{formatMoney(cell.stock_end)}</td>
                            <td>{formatMoney(cell.sales)}</td>
                            <td className={`num ${turnoverToneClass(cell.turnover_percent)}`}>
                              {formatTurnoverPct(cell.turnover_percent)}
                            </td>
                          </Fragment>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
