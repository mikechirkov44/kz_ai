import { useEffect, useMemo, useState } from "react";
import { api, formatMoney } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import { currentQuarterRange, yearQuarterFromIso } from "../months";
import { useStoredPeriod } from "../useStoredPeriod";

type Fact = {
  counterparty_id: string;
  counterparty: string;
  year: number;
  quarter: number;
  fact_amount: number;
  excluded_illiquid_amount: number;
};

export default function FactShipmentsPage() {
  const [cpId, setCpId] = useState("");
  const { from, to, setPeriod } = useStoredPeriod("fact-shipments", currentQuarterRange());
  const [items, setItems] = useState<Fact[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const { year, quarter } = yearQuarterFromIso(from);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    const sp = new URLSearchParams({ year: String(year), quarter: String(quarter) });
    if (cpId) sp.set("counterparty_id", cpId);
    api<{ items: Fact[] }>(`/api/v1/reports/fact-shipments?${sp}`)
      .then((data) => {
        if (!cancelled) setItems(data.items || []);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Ошибка");
        setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cpId, year, quarter]);

  const totals = useMemo(() => {
    return items.reduce(
      (acc, row) => {
        acc.fact += Number(row.fact_amount || 0);
        acc.excluded += Number(row.excluded_illiquid_amount || 0);
        return acc;
      },
      { fact: 0, excluded: 0 },
    );
  }, [items]);

  return (
    <>
      <PageHeader title="Факт отгрузок" subtitle="Участники акции: продажи минус возвраты и неликвид" />
      <div className="panel filters-bar">
        <PeriodPicker
          from={from}
          to={to}
          mode="quarter"
          onChange={(nextFrom, nextTo) => {
            setPeriod(nextFrom, nextTo);
          }}
        />
        <CounterpartySelect
          value={cpId}
          onChange={setCpId}
          promoOnly
          allowEmpty
          compact
          emptyLabel="Все"
        />
      </div>
      {error && <div className="alert">{error}</div>}
      {!loading && items.length > 0 && (
        <p className="muted">
          Участников: {items.length} · факт {formatMoney(totals.fact)} тг · исключено{" "}
          {formatMoney(totals.excluded)} тг
        </p>
      )}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey="fact-shipments"
          rows={items}
          rowKey={(row) => `${row.counterparty_id}-${row.year}-${row.quarter}`}
          loading={loading}
          empty="Нет участников акции"
          emptyHint="Отметьте клиентов звёздочкой ★ на экране Контрагенты."
          emptyAction={{ to: "/counterparties", label: "Открыть контрагентов" }}
          columns={[
            {
              key: "counterparty",
              title: "Контрагент",
              width: 280,
              sticky: true,
              getValue: (row) => row.counterparty,
            },
            {
              key: "period",
              title: "Период",
              width: 140,
              getValue: (row) => `${row.quarter} кв. ${row.year}`,
            },
            {
              key: "fact_amount",
              title: "Факт, тг",
              width: 160,
              align: "right",
              getValue: (row) => row.fact_amount,
              render: (row) => formatMoney(row.fact_amount),
            },
            {
              key: "excluded_illiquid_amount",
              title: "Исключено (неликвид)",
              width: 200,
              align: "right",
              getValue: (row) => row.excluded_illiquid_amount,
              render: (row) => formatMoney(row.excluded_illiquid_amount),
            },
          ]}
        />
      </div>
    </>
  );
}
