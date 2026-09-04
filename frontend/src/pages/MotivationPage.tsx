import { useState } from "react";
import { api, downloadFile, formatMoney, gradeClass } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";

type Report = {
  counterparty: string;
  period: string;
  total_bonus: number;
  items: {
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
  }[];
};

export default function MotivationPage() {
  const [cpId, setCpId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [year, setYear] = useState(2023);
  const [month, setMonth] = useState(1);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    if (!cpId) return;
    setLoading(true);
    setError("");
    try {
      const data = await api<Report>(
        `/api/v1/reports/motivation?counterparty_id=${cpId}&year=${year}&month=${month}`,
      );
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Мотивация"
        subtitle="Как в Excel «Расчёт мотивации»: номенклатура, ЖЦТ, продано, вознаграждение"
        actions={
          <div className="toolbar">
            <button className="btn" onClick={load} disabled={!cpId || loading}>
              {loading ? "Считаем…" : "Сформировать"}
            </button>
            <button
              className="btn secondary"
              disabled={!cpId}
              onClick={() =>
                downloadFile(
                  `/api/v1/reports/motivation.xlsx?counterparty_id=${cpId}&year=${year}&month=${month}`,
                  `motivation_${year}_${month}.xlsx`,
                ).catch((err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"))
              }
            >
              Excel
            </button>
          </div>
        }
      />
      <div className="panel">
        <div className="grid-3" style={{ marginBottom: 14 }}>
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
          <label className="field">
            <span>Год</span>
            <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>Месяц</span>
            <Select
              value={String(month)}
              onChange={(v) => setMonth(Number(v))}
              options={[
                { value: "1", label: "Январь" },
                { value: "2", label: "Февраль" },
                { value: "3", label: "Март" },
                { value: "4", label: "Апрель" },
                { value: "5", label: "Май" },
                { value: "6", label: "Июнь" },
                { value: "7", label: "Июль" },
                { value: "8", label: "Август" },
                { value: "9", label: "Сентябрь" },
                { value: "10", label: "Октябрь" },
                { value: "11", label: "Ноябрь" },
                { value: "12", label: "Декабрь" },
              ]}
            />
          </label>
        </div>
        <CounterpartySelect value={cpId} onChange={setCpId} promoOnly sourceId={sourceId || undefined} />
        {error && <div className="alert" style={{ marginTop: 12 }}>{error}</div>}
      </div>
      {report && (
        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>
              {report.counterparty} · {report.period}
            </h2>
            <span className="pill gold">Итого {formatMoney(report.total_bonus)} тг</span>
          </div>
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
        </div>
      )}
    </>
  );
}
