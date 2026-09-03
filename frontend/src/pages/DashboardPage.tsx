import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";

type Quarterly = {
  year: number;
  quarter: number;
  clients: { counterparty: string; plan: number; fact: number; percent: number }[];
};

export default function DashboardPage() {
  const year = new Date().getFullYear();
  const quarter = Math.floor(new Date().getMonth() / 3) + 1;
  const [data, setData] = useState<Quarterly | null>(null);
  const [health, setHealth] = useState<string>("…");

  useEffect(() => {
    api<Quarterly>(`/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}`)
      .then(setData)
      .catch(() => setData({ year, quarter, clients: [] }));
    api<{ status: string }>("/api/v1/health").then((h) => setHealth(h.status)).catch(() => setHealth("offline"));
  }, [quarter, year]);

  const chart = (data?.clients || []).map((c) => ({
    name: c.counterparty.slice(0, 18),
    plan: Number(c.plan),
    fact: Number(c.fact),
  }));

  return (
    <>
      <h1>Дашборд</h1>
      <p className="muted">План/факт текущего квартала и статус системы</p>
      <div className="panel">
        <span className="pill">API: {health}</span>
        <span className="pill" style={{ marginLeft: 8 }}>Q{quarter} {year}</span>
      </div>
      <div className="panel">
        <h2>План / Факт</h2>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <BarChart data={chart}>
              <XAxis dataKey="name" hide={chart.length > 8} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="plan" fill="#0f4c5c" name="План" />
              <Bar dataKey="fact" fill="#c27c3a" name="Факт" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        {!chart.length && <p className="muted">Нет выставленных квартальных планов</p>}
      </div>
    </>
  );
}
