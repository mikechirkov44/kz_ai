import { useState } from "react";
import { api, formatMoney } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";

type Fact = {
  counterparty: string;
  year: number;
  quarter: number;
  fact_amount: number;
  excluded_illiquid_amount: number;
};

export default function FactShipmentsPage() {
  const [cpId, setCpId] = useState("");
  const [year, setYear] = useState(2023);
  const [quarter, setQuarter] = useState(1);
  const [fact, setFact] = useState<Fact | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    if (!cpId) return;
    setLoading(true);
    setError("");
    try {
      const data = await api<Fact>(
        `/api/v1/reports/fact-shipments?counterparty_id=${cpId}&year=${year}&quarter=${quarter}`,
      );
      setFact(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
      setFact(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Факт отгрузок"
        subtitle="Реализации минус возвраты, с исключением неликвида (ЖЦТ «Вывод»)"
        actions={
          <button className="btn" onClick={load} disabled={!cpId || loading}>
            {loading ? "Считаем…" : "Рассчитать"}
          </button>
        }
      />
      <div className="panel">
        <div className="grid-3" style={{ marginBottom: 14 }}>
          <label className="field">
            <span>Год</span>
            <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>Квартал</span>
            <Select
              value={String(quarter)}
              onChange={(v) => setQuarter(Number(v))}
              options={[
                { value: "1", label: "Q1" },
                { value: "2", label: "Q2" },
                { value: "3", label: "Q3" },
                { value: "4", label: "Q4" },
              ]}
            />
          </label>
        </div>
        <CounterpartySelect value={cpId} onChange={setCpId} allowEmpty />
        {error && <div className="alert" style={{ marginTop: 12 }}>{error}</div>}
      </div>
      {fact && (
        <div className="stats">
          <div className="stat">
            <div className="label">Контрагент</div>
            <div className="value" style={{ fontSize: "1.05rem" }}>
              {fact.counterparty}
            </div>
          </div>
          <div className="stat">
            <div className="label">Период</div>
            <div className="value">
              Q{fact.quarter} {fact.year}
            </div>
          </div>
          <div className="stat">
            <div className="label">Факт, тг</div>
            <div className="value">{formatMoney(fact.fact_amount)}</div>
          </div>
          <div className="stat">
            <div className="label">Исключено (неликвид)</div>
            <div className="value">{formatMoney(fact.excluded_illiquid_amount)}</div>
          </div>
        </div>
      )}
    </>
  );
}
