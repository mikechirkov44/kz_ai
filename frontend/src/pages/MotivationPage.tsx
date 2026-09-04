import { useEffect, useState } from "react";
import { api, downloadFile, formatMoney, gradeClass } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import Select from "../components/Select";
import { monthRange, yearMonthFromIso } from "../months";

type MotivationItem = {
  article: string;
  name?: string;
  lts?: string;
  lts_date?: string;
  price: number;
  quantity: number;
  grade: string;
  bonus_per_unit: number;
  total_bonus: number;
  is_promo_motivation?: boolean;
  counterparty?: string;
};

type ClientRow = {
  counterparty_id: string;
  counterparty: string;
  quantity: number;
  lines: number;
  total_bonus: number;
};

type Report = {
  counterparty: string;
  counterparty_id?: string | null;
  period: string;
  total_bonus: number;
  items: MotivationItem[];
  clients: ClientRow[];
};

const INITIAL = monthRange(2023, 1);

export default function MotivationPage() {
  const [cpId, setCpId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [from, setFrom] = useState(INITIAL.from);
  const [to, setTo] = useState(INITIAL.to);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
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
        title="Мотивация"
        subtitle="Вознаграждение по продажам за месяц"
        actions={
          <button
            className="btn secondary"
            onClick={() =>
              downloadFile(`/api/v1/reports/motivation.xlsx?${query()}`, `motivation_${year}_${String(month).padStart(2, "0")}.xlsx`).catch(
                (err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"),
              )
            }
          >
            Excel
          </button>
        }
      />
      <div className="panel filters-bar grid-3">
        <PeriodPicker
          from={from}
          to={to}
          mode="month"
          onChange={(nextFrom, nextTo) => {
            setFrom(nextFrom);
            setTo(nextTo);
          }}
        />
        <label className="field">
          <span>База 1С</span>
          <Select
            value={sourceId}
            onChange={setSourceId}
            options={[
              { value: "", label: "Все" },
              { value: "asil", label: "asil" },
              { value: "miamor", label: "miamor" },
            ]}
          />
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
      </div>
      {error && <div className="alert">{error}</div>}
      {loading && <p className="muted">Считаем…</p>}
      {report && (
        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>
              {report.counterparty} · {report.period}
            </h2>
            <span className="pill gold">Итого {formatMoney(report.total_bonus)} тг</span>
          </div>
          {summary ? (
            <div style={{ marginTop: 14 }}>
              <DataTable
                storageKey="motivation-clients"
                rows={report.clients}
                rowKey={(row) => row.counterparty_id}
                onRowClick={(row) => setCpId(row.counterparty_id)}
                empty="Нет продаж за период"
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
                    width: 130,
                    align: "right",
                    render: (row) => Number(row.quantity),
                  },
                  {
                    key: "lines",
                    title: "Строк",
                    width: 90,
                    align: "right",
                  },
                  {
                    key: "total_bonus",
                    title: "Итого",
                    width: 140,
                    align: "right",
                    render: (row) => formatMoney(row.total_bonus),
                  },
                ]}
              />
              {!!report.clients.length && <p className="muted">Нажмите строку, чтобы открыть детализацию</p>}
            </div>
          ) : (
            <div style={{ marginTop: 14 }}>
              <DataTable
                storageKey="motivation"
                rows={report.items}
                rowKey={(item, idx) => `${item.article}-${idx}`}
                empty="Нет продаж за период"
                columns={[
                  {
                    key: "article",
                    title: "Номенклатура",
                    width: 220,
                    sticky: true,
                    getValue: (item) => `${item.article} ${item.name || ""}`,
                    render: (item) => (
                      <>
                        {item.article}
                        {item.name ? <div className="muted">{item.name}</div> : null}
                      </>
                    ),
                  },
                  {
                    key: "lts",
                    title: "ЖЦТ",
                    width: 110,
                    getValue: (item) => item.lts || "",
                    render: (item) => item.lts || "—",
                  },
                  {
                    key: "lts_date",
                    title: "Дата ЖЦТ",
                    width: 120,
                    getValue: (item) => item.lts_date || "",
                    render: (item) => item.lts_date || "—",
                  },
                  {
                    key: "price",
                    title: "Цена",
                    width: 110,
                    align: "right",
                    render: (item) => formatMoney(item.price),
                  },
                  {
                    key: "quantity",
                    title: "Продано (шт)",
                    width: 120,
                    align: "right",
                    render: (item) => Number(item.quantity),
                  },
                  {
                    key: "grade",
                    title: "Грейд",
                    width: 90,
                    render: (item) => <span className={gradeClass(item.grade)}>{item.grade}</span>,
                  },
                  {
                    key: "bonus_per_unit",
                    title: "Вознаграждение",
                    width: 130,
                    align: "right",
                    render: (item) => formatMoney(item.bonus_per_unit),
                  },
                  {
                    key: "total_bonus",
                    title: "Итого",
                    width: 120,
                    align: "right",
                    render: (item) => formatMoney(item.total_bonus),
                  },
                ]}
              />
            </div>
          )}
        </div>
      )}
    </>
  );
}
