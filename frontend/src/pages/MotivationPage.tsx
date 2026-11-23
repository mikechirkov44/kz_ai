import { Fragment, useEffect, useRef, useState } from "react";
import { api, downloadFile, formatMoney, gradeClass } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import { useAuth } from "../auth";
import DataTable from "../components/DataTable";
import DatePicker from "../components/DatePicker";
import EmptyState from "../components/EmptyState";
import { ExcelLabel } from "../components/ExcelIcon";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import ReportWait from "../components/ReportWait";
import SourceSelect from "../components/SourceSelect";
import Select from "../components/Select";
import { currentMonthRange, yearMonthFromIso } from "../months";
import { useODataSources } from "../odataSources";
import { useStoredPeriod } from "../useStoredPeriod";

function nomenclatureLabel(article: string, name?: string): string {
  const title = (name || "").trim();
  const art = (article || "").trim();
  if (!title) return art;
  if (art && title.toLowerCase().startsWith(art.toLowerCase())) return title;
  return title;
}

type MotivationItem = {
  article: string;
  name?: string;
  price: number;
  quantity: number;
  grade: string;
  bonus_per_unit: number;
  total_bonus: number;
  is_promo_motivation?: boolean;
  counterparty?: string;
  cost_amount?: number;
  calculated_amount?: number | null;
  difference_percent?: number | null;
};

type MotivationGroup = {
  grade: string;
  bonus_per_unit: number;
  items: MotivationItem[];
  quantity: number;
  total_bonus: number;
  total_cost: number;
  total_calculated_cost: number;
  difference_percent?: number | null;
};

type ClientRow = {
  counterparty_id: string;
  counterparty: string;
  quantity: number;
  lines: number;
  total_bonus: number;
  total_cost?: number;
  total_calculated_cost?: number;
  difference_percent?: number | null;
};

type MotivationClientReport = {
  counterparty: string;
  counterparty_id: string;
  groups: MotivationGroup[];
  total_bonus: number;
  total_cost?: number;
  total_calculated_cost?: number;
  difference_percent?: number | null;
};

type Report = {
  counterparty: string;
  counterparty_id?: string | null;
  period: string;
  total_bonus: number;
  total_cost?: number;
  total_calculated_cost?: number;
  difference_percent?: number | null;
  items: MotivationItem[];
  groups: MotivationGroup[];
  clients: ClientRow[];
  client_reports?: MotivationClientReport[];
};

const UPLOAD_SALES = { to: "/uploads", label: "Загрузить продажи" };

function fmtPct(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${formatMoney(value)}%`;
}

function MotivationDetailTable({
  groups,
  totalBonus,
  totalCost,
  totalCalculated,
  differencePercent,
}: {
  groups: MotivationGroup[];
  totalBonus: number;
  totalCost: number;
  totalCalculated: number;
  differencePercent?: number | null;
}) {
  const gradesKey = groups.map((group) => group.grade).join("\n");
  const [openGrades, setOpenGrades] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setOpenGrades({});
  }, [gradesKey]);

  function isOpen(grade: string): boolean {
    return openGrades[grade] !== false;
  }

  function toggleGrade(grade: string) {
    setOpenGrades((prev) => ({ ...prev, [grade]: prev[grade] === false }));
  }

  function setAll(open: boolean) {
    setOpenGrades(Object.fromEntries(groups.map((group) => [group.grade, open])));
  }

  const allOpen = groups.length > 0 && groups.every((group) => isOpen(group.grade));

  return (
    <div className="table-wrap" style={{ marginTop: 14 }}>
      {groups.length > 0 ? (
        <div className="rec-fold-bar">
          <button type="button" className="btn ghost sm" onClick={() => setAll(true)} disabled={allOpen}>
            Развернуть все
          </button>
          <button type="button" className="btn ghost sm" onClick={() => setAll(false)} disabled={!allOpen}>
            Свернуть все
          </button>
        </div>
      ) : null}
      <table>
        <thead>
          <tr>
            <th className="sticky">Ценовые диапазоны / Номенклатура</th>
            <th className="num">Продано (шт)</th>
            <th className="num">Вознаграждение</th>
            <th className="num">Итого вознаграждение</th>
            <th className="num">Стоимость</th>
            <th className="num">Стоимость расчётная</th>
            <th className="num">Разница %</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => {
            const open = isOpen(group.grade);
            return (
              <Fragment key={group.grade}>
                <tr
                  className={`motivation-group-row ${open ? "is-open" : "is-collapsed"}`}
                  onClick={() => toggleGrade(group.grade)}
                >
                  <td className="sticky">
                    <button
                      type="button"
                      className="motivation-group-toggle"
                      aria-expanded={open}
                      onClick={(event) => {
                        event.stopPropagation();
                        toggleGrade(group.grade);
                      }}
                    >
                      <span className="rec-group-caret" aria-hidden="true">
                        {open ? "▾" : "▸"}
                      </span>
                      <span className={gradeClass(group.grade)}>{group.grade}</span>
                      {group.grade !== "Доп. мотивация" && (
                        <span className="muted">{formatMoney(group.bonus_per_unit)} / шт</span>
                      )}
                    </button>
                  </td>
                  <td className="num">{Number(group.quantity)}</td>
                  <td className="num">{formatMoney(group.bonus_per_unit)}</td>
                  <td className="num">{formatMoney(group.total_bonus)}</td>
                  <td className="num">{formatMoney(group.total_cost)}</td>
                  <td className="num">{formatMoney(group.total_calculated_cost || 0)}</td>
                  <td className="num">{fmtPct(group.difference_percent)}</td>
                </tr>
                {open
                  ? group.items.map((item, idx) => (
                      <tr key={`${group.grade}-${item.article}-${idx}`}>
                        <td className="sticky">{nomenclatureLabel(item.article, item.name)}</td>
                        <td className="num">{Number(item.quantity)}</td>
                        <td className="num">{formatMoney(item.bonus_per_unit)}</td>
                        <td className="num">{formatMoney(item.total_bonus)}</td>
                        <td className="num">{formatMoney(item.cost_amount || 0)}</td>
                        <td className="num">
                          {item.calculated_amount != null ? formatMoney(item.calculated_amount) : "—"}
                        </td>
                        <td className="num">{fmtPct(item.difference_percent)}</td>
                      </tr>
                    ))
                  : null}
              </Fragment>
            );
          })}
          <tr style={{ fontWeight: 600 }}>
            <td className="sticky">Итого</td>
            <td className="num">{groups.reduce((sum, group) => sum + Number(group.quantity || 0), 0)}</td>
            <td className="num" />
            <td className="num">{formatMoney(totalBonus)}</td>
            <td className="num">{formatMoney(totalCost)}</td>
            <td className="num">{formatMoney(totalCalculated)}</td>
            <td className="num">{fmtPct(differencePercent)}</td>
          </tr>
        </tbody>
      </table>
      {!groups.length && (
        <EmptyState
          title="Нет продаж за период"
          hint="Загрузите Excel продаж за выбранный месяц."
          action={UPLOAD_SALES}
        />
      )}
    </div>
  );
}

type Rule = {
  counterparty_id: string;
  counterparty: string;
  source_id: string;
  effective_month: string | null;
  category: "exit" | "all" | null;
  bonus: string | null;
};

function MotivationRules({ onChange, canClose }: { onChange: () => void; canClose: boolean }) {
  const { sources, labelOf } = useODataSources();
  const [rows, setRows] = useState<Rule[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [client, setClient] = useState("");
  const [category, setCategory] = useState<NonNullable<Rule["category"]>>("exit");
  const [effectiveMonth, setEffectiveMonth] = useState(() => currentMonthRange().from.slice(0, 7));
  const [bonus, setBonus] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [fileVersion, setFileVersion] = useState(0);
  const [imported, setImported] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endpoint = "/api/v1/reports/motivation/rules";
  const [closedThrough, setClosedThrough] = useState("");
  const closed = Boolean(closedThrough && effectiveMonth <= closedThrough);

  useEffect(() => {
    api<Rule[]>(endpoint).then(setRows).catch((err: Error) => setError(err.message));
    api<{ closed_through: string | null }>(`${endpoint}/closed-through`)
      .then((result) => setClosedThrough(result.closed_through?.slice(0, 7) || ""))
      .catch((err: Error) => setError(err.message));
  }, []);

  async function closeMonth() {
    if (!window.confirm(`Закрыть изменение ставок по ${effectiveMonth} включительно?`)) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ closed_through: string }>(
        `${endpoint}/closed-through?effective_month=${effectiveMonth}-01`, { method: "PUT" },
      );
      setClosedThrough(result.closed_through.slice(0, 7));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка закрытия месяца");
    } finally {
      setBusy(false);
    }
  }

  async function save(id: string, remove = false) {
    setBusy(true);
    setError("");
    try {
      await api<void>(`${endpoint}/${id}?effective_month=${effectiveMonth}-01`, remove
        ? { method: "DELETE" }
        : { method: "PUT", body: JSON.stringify({ category, bonus }) });
      onChange();
      setRows(await api<Rule[]>(endpoint));
      if (id === client) {
        setClient("");
        setBonus("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  }

  const categoryLabels = { exit: "Только на Вывод", all: "На весь ассортимент" };

  async function importFile() {
    if (!file) return;
    setBusy(true);
    setError("");
    setImported(null);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("effective_month", `${effectiveMonth}-01`);
      const result = await api<{ imported: number }>(`${endpoint}/import`, { method: "POST", body });
      setImported(result.imported);
      setFile(null);
      setFileVersion((value) => value + 1);
      setClient("");
      setBonus("");
      onChange();
      setRows(await api<Rule[]>(endpoint));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка импорта ставок");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="panel motivation-rates" open>
      <summary>Настройки дополнительной мотивации</summary>
      <div className="motivation-rates-body">
      {error && <div className="alert">{error}</div>}
      {imported !== null && <p role="status">Ставок загружено: {imported}</p>}
      <label className="field motivation-rates-month">
        <span>Месяц начала действия</span>
        <DatePicker mode="month" value={`${effectiveMonth}-01`} disabled={busy}
          onChange={(value) => setEffectiveMonth(value.slice(0, 7))} />
      </label>
      {closedThrough && <p role="status">Ставки закрыты по {closedThrough} включительно.</p>}
      {canClose && <div>
        <button type="button" className="btn secondary" onClick={closeMonth}
          disabled={busy || closed || effectiveMonth >= currentMonthRange().from.slice(0, 7)}>
          Закрыть ставки по выбранный месяц
        </button>
      </div>}
      <div className="motivation-rates-editors">
      <form className="motivation-rates-editor motivation-rates-import" onSubmit={(event) => { event.preventDefault(); void importFile(); }}>
        <h3>Импорт из Excel</h3>
        <div className="field">
          <span>Файл со ставками (.xlsx)</span>
          <input key={fileVersion} ref={fileInput} type="file" accept=".xlsx" hidden disabled={busy}
            onChange={(event) => { setFile(event.target.files?.[0] || null); setImported(null); }} />
          <button className="motivation-file-picker" type="button" disabled={busy} onClick={() => fileInput.current?.click()}>
            <span className="motivation-file-action">{file ? "Заменить файл" : "Выбрать файл"}</span>
            {file && <span className="motivation-file-name" title={file.name}>{file.name}</span>}
          </button>
        </div>
        <button type="submit" className="btn" disabled={busy || closed || !file || !effectiveMonth}>Загрузить ставки</button>
        <button type="button" className="btn secondary" onClick={() => {
          downloadFile(`${endpoint}/template.xlsx`, "motivation-rules-template.xlsx")
            .catch((err: Error) => setError(err.message));
        }}>
          <ExcelLabel>Скачать шаблон ставок</ExcelLabel>
        </button>
      </form>
      <form className="motivation-rates-editor" onSubmit={(event) => { event.preventDefault(); void save(client); }}>
        <h3>Ставка клиента</h3>
        <label className="field">
          <span>Организация</span>
          <SourceSelect value={sourceId} sources={sources} emptyLabel="Все организации"
            onChange={(id) => { setSourceId(id); setClient(""); }} />
        </label>
        <CounterpartySelect key={sourceId} value={client} sourceId={sourceId || undefined} promoOnly allowEmpty
          onChange={(id) => {
            setClient(id);
            const rule = rows.find((row) =>
              row.counterparty_id === id && (!row.effective_month || row.effective_month.slice(0, 7) <= effectiveMonth)
            );
            setCategory(rule?.category || "exit");
            setBonus(rule?.bonus || "");
          }}
        />
        <label className="field">
          <span>Вид мотивации</span>
          <Select value={category} options={[
            { value: "exit", label: categoryLabels.exit },
            { value: "all", label: categoryLabels.all },
          ]} onChange={(value) => setCategory(value as NonNullable<Rule["category"]>)} />
        </label>
        <label className="field">
          <span>Вознаграждение за штуку</span>
          <input type="number" min="0" step="0.01" required value={bonus} onChange={(event) => setBonus(event.target.value)} />
        </label>
        <button className="btn" disabled={busy || closed || !client || !effectiveMonth}>Сохранить</button>
        <button type="button" className="btn secondary" disabled={busy || closed || !client || !effectiveMonth} onClick={() => {
          if (window.confirm(`Применять стандартный расчёт с месяца ${effectiveMonth}?`)) void save(client, true);
        }}>Вернуть стандартный расчёт</button>
      </form>
      </div>
      <section className="motivation-rates-history">
      <h3>История ставок</h3>
      {rows.length > 0 && (
        <div className="motivation-rates-table"><table>
          <thead><tr><th>Организация</th><th>Головной контрагент</th><th>Действует с</th><th>Вид мотивации</th><th>Вознаграждение за штуку</th><th>Действия</th></tr></thead>
          <tbody>{rows.map((row) => (
            <tr key={`${row.counterparty_id}-${row.effective_month ?? "initial"}`}>
              <td>{labelOf(row.source_id)}</td><td>{row.counterparty}</td>
              <td>{row.effective_month?.slice(0, 7) || "Исходная ставка"}</td>
              <td><span className={row.category ? "motivation-rate-kind is-custom" : "motivation-rate-kind"}>
                {row.category ? categoryLabels[row.category] : "Стандартный расчёт"}
              </span></td>
              <td className="motivation-rate-amount">{row.bonus === null ? "—" : formatMoney(row.bonus)}</td>
              <td>
                <button type="button" className="btn secondary" disabled={busy} onClick={() => {
                  setSourceId(row.source_id);
                  setClient(row.counterparty_id);
                  if (row.effective_month) setEffectiveMonth(row.effective_month.slice(0, 7));
                  setCategory(row.category || "exit");
                  setBonus(row.bonus || "");
                }}>Заполнить форму</button>
              </td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      {!rows.length && !error && <p className="muted">Ставок пока нет.</p>}
      </section>
      </div>
    </details>
  );
}

export default function MotivationPage() {
  const { me } = useAuth();
  const [revision, setRevision] = useState(0);
  const { sources } = useODataSources();
  const [cpIds, setCpIds] = useState<string[]>([]);
  const [sourceId, setSourceId] = useState("");
  const { from, to, setPeriod } = useStoredPeriod("motivation", currentMonthRange());
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const { year, month } = yearMonthFromIso(from);

  function query(): string {
    const sp = new URLSearchParams({ year: String(year), month: String(month) });
    for (const id of cpIds) sp.append("counterparty_ids", id);
    if (sourceId) sp.set("source_id", sourceId);
    return sp.toString();
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api<Report>(`/api/v1/reports/motivation?${query()}`)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Ошибка");
        setReport(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cpIds, sourceId, year, month, revision]);

  const summary = !cpIds.length;

  return (
    <>
      <PageHeader
        title="Мотивационные акции"
        subtitle="Вознаграждение по продажам за месяц"
      />
      {me && ["admin", "regional_director", "analytic"].includes(me.role) && (
        <MotivationRules canClose={me.role === "admin"} onChange={() => setRevision((value) => value + 1)} />
      )}
      <div className="panel filters-bar">
        <PeriodPicker
          from={from}
          to={to}
          mode="month"
          onChange={(nextFrom, nextTo) => {
            setPeriod(nextFrom, nextTo);
          }}
        />
        <label className="field">
          <span>База 1С</span>
          <SourceSelect value={sourceId} onChange={setSourceId} sources={sources} />
        </label>
        <CounterpartySelect
          multiple
          value={cpIds}
          onChange={setCpIds}
          sourceId={sourceId || undefined}
          allowEmpty
          compact
          emptyLabel="Все"
        />
        <div className="filters-actions">
          <button
            className="btn secondary"
            type="button"
            disabled={loading}
            onClick={() =>
              downloadFile(
                `/api/v1/reports/motivation.xlsx?${query()}`,
                `motivation_${year}_${String(month).padStart(2, "0")}.xlsx`,
              ).catch((err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"))
            }
          >
            <ExcelLabel>Excel</ExcelLabel>
          </button>
        </div>
      </div>
      {error && <div className="alert">{error}</div>}
      {loading && <ReportWait compact={!!report} title={report ? "Обновляю отчёт" : "Считаю мотивацию"} />}
      {loading && !report && (
        <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
          <DataTable
            loading
            rows={[]}
            rowKey={() => "skel"}
            empty="Нет продаж за период"
            columns={[
              { key: "counterparty", title: "Контрагент", width: 280, sticky: true },
              { key: "quantity", title: "Продано (шт)", width: 120, align: "right" },
              { key: "total_bonus", title: "Вознаграждение", width: 140, align: "right" },
              { key: "total_cost", title: "Стоимость", width: 130, align: "right" },
              { key: "total_calculated_cost", title: "Расчётная", width: 130, align: "right" },
              { key: "difference_percent", title: "Разница %", width: 110, align: "right" },
            ]}
          />
        </div>
      )}
      {!loading && !report && !error && (
        <div className="panel">
          <EmptyState
            title="Нет продаж за период"
            hint="Загрузите Excel продаж за выбранный месяц — без этого мотивацию считать не из чего."
            action={UPLOAD_SALES}
          />
        </div>
      )}
      {report && (
        <div className={`panel ${loading ? "report-refreshing" : ""}`}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              {!summary && (
                <button className="btn secondary sm" type="button" onClick={() => setCpIds([])}>
                  ← Ко всем клиентам
                </button>
              )}
              <h2 style={{ margin: summary ? 0 : "8px 0 0" }}>
                {report.counterparty} · {report.period}
              </h2>
            </div>
            <div className="toolbar" style={{ gap: 8, flexWrap: "wrap" }}>
              <span className="pill gold">Вознаграждение {formatMoney(report.total_bonus)}</span>
              <span className="pill">Стоимость {formatMoney(report.total_cost || 0)}</span>
              <span className="pill">Расчётная {formatMoney(report.total_calculated_cost || 0)}</span>
              <span className="pill">{fmtPct(report.difference_percent)}</span>
            </div>
          </div>
          {summary ? (
            <div style={{ marginTop: 14 }}>
              <DataTable
                storageKey="motivation-clients"
                rows={report.clients}
                rowKey={(row) => row.counterparty_id}
                onRowClick={(row) => setCpIds([row.counterparty_id])}
                empty="Нет продаж за период"
                emptyHint="Загрузите Excel продаж за выбранный месяц."
                emptyAction={UPLOAD_SALES}
                columns={[
                  {
                    key: "counterparty",
                    title: "Контрагент",
                    width: 280,
                    sticky: true,
                    getValue: (row) => row.counterparty,
                  },
                  {
                    key: "quantity",
                    title: "Продано (шт)",
                    width: 120,
                    align: "right",
                    render: (row) => Number(row.quantity),
                  },
                  {
                    key: "total_bonus",
                    title: "Вознаграждение",
                    width: 140,
                    align: "right",
                    render: (row) => formatMoney(row.total_bonus),
                  },
                  {
                    key: "total_cost",
                    title: "Стоимость",
                    width: 130,
                    align: "right",
                    render: (row) => formatMoney(row.total_cost || 0),
                  },
                  {
                    key: "total_calculated_cost",
                    title: "Расчётная",
                    width: 130,
                    align: "right",
                    render: (row) => formatMoney(row.total_calculated_cost || 0),
                  },
                  {
                    key: "difference_percent",
                    title: "Разница %",
                    width: 110,
                    align: "right",
                    render: (row) => fmtPct(row.difference_percent),
                  },
                ]}
              />
              {!!report.clients.length && <p className="muted">Нажмите строку, чтобы открыть детализацию</p>}
            </div>
          ) : (
            <>
              {(report.client_reports?.length ? report.client_reports : [
                {
                  counterparty: report.counterparty,
                  counterparty_id: report.counterparty_id || "one",
                  groups: report.groups || [],
                  total_bonus: report.total_bonus,
                  total_cost: report.total_cost,
                  total_calculated_cost: report.total_calculated_cost,
                  difference_percent: report.difference_percent,
                },
              ]).map((client) => (
                <div key={client.counterparty_id}>
                  {(report.client_reports?.length || 0) > 1 && (
                    <h3 style={{ margin: "18px 0 0" }}>{client.counterparty}</h3>
                  )}
                  <MotivationDetailTable
                    groups={client.groups || []}
                    totalBonus={client.total_bonus}
                    totalCost={client.total_cost || 0}
                    totalCalculated={client.total_calculated_cost || 0}
                    differencePercent={client.difference_percent}
                  />
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </>
  );
}
