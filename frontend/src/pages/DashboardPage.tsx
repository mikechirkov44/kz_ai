import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, formatMoney, listCounterparties } from "../api";
import PageHeader from "../components/PageHeader";

type Quarterly = {
  year: number;
  quarter: number;
  clients: { counterparty: string; plan: number; fact: number; percent: number }[];
};

export default function DashboardPage() {
  const year = new Date().getFullYear();
  const quarter = Math.floor(new Date().getMonth() / 3) + 1;
  const [data, setData] = useState<Quarterly | null>(null);
  const [health, setHealth] = useState("…");
  const [promoCount, setPromoCount] = useState(0);
  const [odata, setOdata] = useState<Record<string, string>>({});

  useEffect(() => {
    api<Quarterly>(`/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}`)
      .then(setData)
      .catch(() => setData({ year, quarter, clients: [] }));
    api<{ status: string; odata: Record<string, string> }>("/api/v1/health")
      .then((h) => {
        setHealth(h.status);
        setOdata(h.odata || {});
      })
      .catch(() => setHealth("offline"));
    listCounterparties({ promo_only: true })
      .then((rows) => setPromoCount(rows.length))
      .catch(() => setPromoCount(0));
  }, [quarter, year]);

  const chart = (data?.clients || []).slice(0, 12).map((c) => ({
    name: c.counterparty.slice(0, 16),
    plan: Number(c.plan),
    fact: Number(c.fact),
  }));
  const avgPercent =
    data?.clients?.length
      ? data.clients.reduce((s, c) => s + Number(c.percent || 0), 0) / data.clients.length
      : 0;

  return (
    <>
      <PageHeader
        title="Дашборд"
        subtitle="Сводка по текущему кварталу и состоянию интеграций"
      />
      <div className="stats">
        <div className="stat">
          <div className="label">API</div>
          <div className="value">
            <span className={`pill ${health === "ok" ? "ok" : "warn"}`}>{health}</span>
          </div>
        </div>
        <div className="stat">
          <div className="label">Период</div>
          <div className="value">
            Q{quarter} {year}
          </div>
        </div>
        <div className="stat">
          <div className="label">Участники акции</div>
          <div className="value">{promoCount}</div>
        </div>
        <div className="stat">
          <div className="label">Ср. % плана</div>
          <div className="value">{avgPercent.toFixed(1)}%</div>
        </div>
      </div>
      <div className="panel">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {Object.entries(odata).map(([k, v]) => (
            <span key={k} className={`pill ${v === "ok" ? "ok" : "warn"}`}>
              OData {k}: {v}
            </span>
          ))}
        </div>
        <h2>План / Факт</h2>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <BarChart data={chart}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.08)" />
              <XAxis dataKey="name" hide={chart.length > 8} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => formatMoney(v)} />
              <Bar dataKey="plan" fill="#0f766e" name="План" radius={[4, 4, 0, 0]} />
              <Bar dataKey="fact" fill="#c4a574" name="Факт" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        {!chart.length && (
          <p className="empty">Нет выставленных квартальных планов — добавьте их на экране «Квартальные планы».</p>
        )}
      </div>
    </>
  );
}
