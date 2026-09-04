import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, formatMoney, listCounterparties } from "../api";
import PageHeader from "../components/PageHeader";

type Quarterly = {
  year: number;
  quarter: number;
  clients: { counterparty: string; plan: number; fact: number; percent: number }[];
};

type RecItem = {
  type: string;
  severity: string;
  counterparty?: string;
  article?: string;
  message: string;
};

export default function DashboardPage() {
  const year = new Date().getFullYear();
  const quarter = Math.floor(new Date().getMonth() / 3) + 1;
  const [data, setData] = useState<Quarterly | null>(null);
  const [health, setHealth] = useState("…");
  const [promoCount, setPromoCount] = useState(0);
  const [odata, setOdata] = useState<Record<string, string>>({});
  const [recs, setRecs] = useState<RecItem[]>([]);
  const [recsError, setRecsError] = useState("");

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
    api<{ items: RecItem[] }>("/api/v1/reports/recommendations")
      .then((r) => setRecs(r.items || []))
      .catch((err) => setRecsError(err instanceof Error ? err.message : "Нет рекомендаций"));
  }, [quarter, year]);

  const clients = data?.clients || [];
  const chart = clients.slice(0, 12).map((c) => ({
    name: c.counterparty.slice(0, 16),
    plan: Number(c.plan),
    fact: Number(c.fact),
  }));
  const avgPercent = clients.length
    ? clients.reduce((s, c) => s + Number(c.percent || 0), 0) / clients.length
    : 0;
  const behind = [...clients]
    .filter((c) => Number(c.percent) < 100)
    .sort((a, b) => Number(a.percent) - Number(b.percent))
    .slice(0, 5);
  const ahead = [...clients]
    .filter((c) => Number(c.percent) >= 100)
    .sort((a, b) => Number(b.percent) - Number(a.percent))
    .slice(0, 5);
  const topRecs = [...recs]
    .sort((a, b) => {
      const rank = (s: string) => (s === "high" ? 0 : s === "medium" ? 1 : 2);
      return rank(a.severity) - rank(b.severity);
    })
    .slice(0, 5);
  const highCount = recs.filter((r) => r.severity === "high").length;

  return (
    <>
      <PageHeader
        title="Дашборд"
        subtitle="Сводка по текущему кварталу, интеграциям и рекомендациям"
        actions={
          <div className="toolbar">
            <Link className="btn secondary" to="/uploads">
              Загрузка Excel
            </Link>
            <Link className="btn secondary" to="/quarterly">
              Кварталы
            </Link>
            <Link className="btn" to="/recommendations">
              Рекомендации
            </Link>
          </div>
        }
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
        <div className="stat">
          <div className="label">Рекомендации high</div>
          <div className="value">{highCount}</div>
        </div>
      </div>

      <div className="panel">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
          {Object.entries(odata).map(([k, v]) => (
            <span key={k} className={`pill ${v === "ok" ? "ok" : "warn"}`}>
              OData {k}: {v}
            </span>
          ))}
          {!Object.keys(odata).length && <span className="muted">Статус OData появится после health-check</span>}
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>План / Факт</h2>
            <Link className="muted" to="/quarterly">
              Открыть →
            </Link>
          </div>
          <div style={{ width: "100%", height: 280 }}>
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
            <p className="empty">
              Нет квартальных планов — добавьте на экране <Link to="/quarterly">Квартальные планы</Link>.
            </p>
          )}
        </div>

        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
            <h2 style={{ margin: 0 }}>Рекомендации</h2>
            <Link className="muted" to="/recommendations">
              Все →
            </Link>
          </div>
          {recsError && !topRecs.length && <p className="muted">{recsError}</p>}
          {!recsError && !topRecs.length && (
            <p className="empty">Пока нет сигналов — нужны продажи/остатки и акционные клиенты.</p>
          )}
          <div className="dash-rec-list">
            {topRecs.map((item, idx) => (
              <div key={idx} className={`dash-rec-item ${item.severity}`}>
                <div className="toolbar" style={{ marginBottom: 4 }}>
                  <span className="pill">{item.type}</span>
                  <span
                    className={`pill ${item.severity === "high" ? "bad" : item.severity === "medium" ? "warn" : "ok"}`}
                  >
                    {item.severity}
                  </span>
                </div>
                {(item.counterparty || item.article) && (
                  <div className="muted" style={{ fontSize: "0.85rem", marginBottom: 4 }}>
                    {item.counterparty}
                    {item.article ? ` · ${item.article}` : ""}
                  </div>
                )}
                <div>{item.message}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Отстающие (&lt; 100%)</h2>
          {!behind.length && <p className="empty">Нет данных</p>}
          <ul className="dash-list">
            {behind.map((c) => (
              <li key={c.counterparty}>
                <span>{c.counterparty}</span>
                <strong>{Number(c.percent).toFixed(1)}%</strong>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Выполняют план</h2>
          {!ahead.length && <p className="empty">Нет данных</p>}
          <ul className="dash-list">
            {ahead.map((c) => (
              <li key={c.counterparty}>
                <span>{c.counterparty}</span>
                <strong>{Number(c.percent).toFixed(1)}%</strong>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="panel">
        <h2>Быстрый старт</h2>
        <div className="toolbar">
          <Link className="btn secondary" to="/motivation">
            Мотивация
          </Link>
          <Link className="btn secondary" to="/turnover">
            Оборачиваемость
          </Link>
          <Link className="btn secondary" to="/documents">
            Журнал 1С
          </Link>
          <Link className="btn secondary" to="/admin">
            Админ / sync
          </Link>
        </div>
      </div>
    </>
  );
}
