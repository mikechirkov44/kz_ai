import { useEffect, useState } from "react";
import { api, formatMoney } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import { quarterRange, yearQuarterFromIso } from "../months";

type Fact = {
  counterparty: string;
  year: number;
  quarter: number;
  fact_amount: number;
  excluded_illiquid_amount: number;
};

const INITIAL = quarterRange(2023, 1);

export default function FactShipmentsPage() {
  const [cpId, setCpId] = useState("");
  const [from, setFrom] = useState(INITIAL.from);
  const [to, setTo] = useState(INITIAL.to);
  const [fact, setFact] = useState<Fact | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { year, quarter } = yearQuarterFromIso(from);

  useEffect(() => {
    if (!cpId) {
      setFact(null);
      setError("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    api<Fact>(`/api/v1/reports/fact-shipments?counterparty_id=${cpId}&year=${year}&quarter=${quarter}`)
      .then((data) => {
        if (!cancelled) setFact(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Ошибка");
        setFact(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cpId, year, quarter]);

  return (
    <>
      <PageHeader
        title="Факт отгрузок"
        subtitle="Продажи минус возвраты и неликвид"
      />
      <div className="panel filters-bar grid-2">
        <PeriodPicker
          from={from}
          to={to}
          mode="quarter"
          onChange={(nextFrom, nextTo) => {
            setFrom(nextFrom);
            setTo(nextTo);
          }}
        />
        <CounterpartySelect value={cpId} onChange={setCpId} allowEmpty compact />
      </div>
      {error && <div className="alert">{error}</div>}
      {!cpId && <p className="muted">Выберите контрагента — сумма посчитается сразу</p>}
      {cpId && loading && <p className="muted">Считаем…</p>}
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
              {fact.quarter} кв. {fact.year}
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
