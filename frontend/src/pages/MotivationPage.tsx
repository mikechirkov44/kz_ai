import { Fragment, useEffect, useState } from "react";
import { api, downloadFile, formatMoney, gradeClass } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import DataTable from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import { ExcelLabel } from "../components/ExcelIcon";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import SourceSelect from "../components/SourceSelect";
import { currentMonthRange, yearMonthFromIso } from "../months";
import { useODataSources } from "../odataSources";
import { useStoredPeriod } from "../useStoredPeriod";

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
};

const UPLOAD_SALES = { to: "/uploads", label: "Загрузить продажи" };

function fmtPct(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${formatMoney(value)}%`;
}

export default function MotivationPage() {
  const { sources } = useODataSources();
  const [cpId, setCpId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const { from, to, setPeriod } = useStoredPeriod("motivation", currentMonthRange());
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const { year, month } = yearMonthFromIso(from);

  function query(): string {
    const sp = new URLSearchParams({ year: String(year), month: String(month) });
    if (cpId) sp.set("counterparty_id", cpId);
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
  }, [cpId, sourceId, year, month]);

  const summary = !cpId;

  return (
    <>
      <PageHeader
        title="Мотивационные акции"
        subtitle="Вознаграждение по продажам за месяц — как в отчёте 1С"
      />
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
          value={cpId}
          onChange={setCpId}
          promoOnly
          sourceId={sourceId || undefined}
          allowEmpty
          compact
          emptyLabel="Все"
        />
        <div className="filters-actions">
          <button
            className="btn secondary"
            type="button"
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
        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              {!summary && (
                <button className="btn secondary sm" type="button" onClick={() => setCpId("")}>
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
                onRowClick={(row) => setCpId(row.counterparty_id)}
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
            <div className="table-wrap" style={{ marginTop: 14 }}>
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
                  {(report.groups || []).map((group) => (
                    <Fragment key={group.grade}>
                      <tr className="motivation-group-row">
                        <td className="sticky">
                          <span className={gradeClass(group.grade)}>{group.grade}</span>
                          <span className="muted" style={{ marginLeft: 8 }}>
                            {formatMoney(group.bonus_per_unit)} / шт
                          </span>
                        </td>
                        <td className="num">{Number(group.quantity)}</td>
                        <td className="num">{formatMoney(group.bonus_per_unit)}</td>
                        <td className="num">{formatMoney(group.total_bonus)}</td>
                        <td className="num">{formatMoney(group.total_cost)}</td>
                        <td className="num">{formatMoney(group.total_calculated_cost || 0)}</td>
                        <td className="num">{fmtPct(group.difference_percent)}</td>
                      </tr>
                      {group.items.map((item, idx) => (
                        <tr key={`${group.grade}-${item.article}-${idx}`}>
                          <td className="sticky">
                            {item.article}
                            {item.name ? <div className="muted">{item.name}</div> : null}
                          </td>
                          <td className="num">{Number(item.quantity)}</td>
                          <td className="num">{formatMoney(item.bonus_per_unit)}</td>
                          <td className="num">{formatMoney(item.total_bonus)}</td>
                          <td className="num">{formatMoney(item.cost_amount || 0)}</td>
                          <td className="num">
                            {item.calculated_amount != null ? formatMoney(item.calculated_amount) : "—"}
                          </td>
                          <td className="num">{fmtPct(item.difference_percent)}</td>
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                  <tr style={{ fontWeight: 600 }}>
                    <td className="sticky">Итого</td>
                    <td className="num" />
                    <td className="num" />
                    <td className="num">{formatMoney(report.total_bonus)}</td>
                    <td className="num">{formatMoney(report.total_cost || 0)}</td>
                    <td className="num">{formatMoney(report.total_calculated_cost || 0)}</td>
                    <td className="num">{fmtPct(report.difference_percent)}</td>
                  </tr>
                </tbody>
              </table>
              {!report.groups?.length && (
                <EmptyState
                  title="Нет продаж за период"
                  hint="Загрузите Excel продаж за выбранный месяц."
                  action={UPLOAD_SALES}
                />
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}
