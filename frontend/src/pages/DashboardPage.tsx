import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, canSeeAdmin, formatMoney, listCounterparties } from "../api";
import { useAuth } from "../auth";
import CountUp from "../components/CountUp";
import CbrRates, { type CbrRatesResponse } from "../components/CbrRates";
import DashDonut from "../components/DashDonut";
import DwellHeatmap from "../components/DwellHeatmap";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import { dwellBucketChart, planPercentChart, recSeverityChart, workTypeChart } from "../dashboardCharts";
import { currentQuarterRange, yearQuarterFromIso } from "../months";
import { useODataSources } from "../odataSources";
import { type Recommendation } from "../recommendations";
import type { HeatmapCell, HeatmapCounterparty } from "../heatmapRows";

type Quarterly = {
  year: number;
  quarter: number;
  clients: {
    counterparty: string;
    plan: number;
    fact: number;
    percent: number;
    work_type?: string | null;
    work_type_label?: string | null;
  }[];
};

const CHART_TOOLTIP = {
  borderRadius: 12,
  border: "1px solid var(--line)",
  background: "var(--surface)",
  boxShadow: "var(--shadow-lg)",
};

type RecItem = Recommendation;

type Heatmap = {
  counterparties: HeatmapCounterparty[];
  articles: string[];
  article_names?: Record<string, string>;
  cells: HeatmapCell[];
};

export default function DashboardPage() {
  const [from, setFrom] = useState(() => currentQuarterRange().from);
  const [to, setTo] = useState(() => currentQuarterRange().to);
  const { year, quarter } = yearQuarterFromIso(from);
  const { me } = useAuth();
  const { labelOf } = useODataSources();
  const [data, setData] = useState<Quarterly | null>(null);
  const [promoCount, setPromoCount] = useState(0);
  const [recs, setRecs] = useState<RecItem[]>([]);
  const [recsError, setRecsError] = useState("");
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);
  const [cbr, setCbr] = useState<CbrRatesResponse | null>(null);

  useEffect(() => {
    api<Quarterly>(`/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}`)
      .then(setData)
      .catch(() => setData({ year, quarter, clients: [] }));
  }, [quarter, year]);

  useEffect(() => {
    listCounterparties({ promo_only: true })
      .then((rows) => setPromoCount(rows.length))
      .catch(() => setPromoCount(0));
    api<{ items: RecItem[] }>("/api/v1/reports/recommendations")
      .then((r) => setRecs(r.items || []))
      .catch((err) => setRecsError(err instanceof Error ? err.message : "Нет рекомендаций"));
    api<Heatmap>("/api/v1/reports/dwell-heatmap")
      .then(setHeatmap)
      .catch(() => setHeatmap({ counterparties: [], articles: [], cells: [] }));
    api<CbrRatesResponse>("/api/v1/reports/cbr-rates")
      .then(setCbr)
      .catch(() => setCbr({ status: "error", items: [] }));
  }, []);

  const clients = data?.clients || [];
  const chart = clients.slice(0, 12).map((c) => ({
    name: c.counterparty.slice(0, 16),
    plan: Number(c.plan),
    fact: Number(c.fact),
  }));
  const avgPercent = clients.length
    ? clients.reduce((s, c) => s + Number(c.percent || 0), 0) / clients.length
    : 0;
  const highCount = recs.filter((r) => r.severity === "high").length;
  const workSlices = workTypeChart(clients);
  const dwellSlices = dwellBucketChart(heatmap?.cells || []);
  const recSlices = recSeverityChart(recs);
  const percentRows = planPercentChart(
    clients.map((c) => ({ counterparty: c.counterparty, percent: Number(c.percent) })),
  );

  return (
    <>
      <PageHeader
        title="Дашборд"
        subtitle="Сводка по выбранному кварталу и рекомендациям"
        actions={
          <div className="toolbar">
            <Link className="help-link" to="/help">
              Справка
            </Link>
            <Link className="btn secondary" to="/uploads">
              Ввод данных
            </Link>
            <Link className="btn secondary" to="/quarterly">
              Квартальные отчеты
            </Link>
            <Link className="btn" to="/recommendations">
              Рекомендации
            </Link>
          </div>
        }
      />

      <CbrRates data={cbr} />

      <div className="stats">
        <div className="stat stat-period">
          <PeriodPicker
            from={from}
            to={to}
            mode="quarter"
            minYear={2023}
            triggerLabel={`Q${quarter} ${year}`}
            onChange={(nextFrom, nextTo) => {
              setFrom(nextFrom);
              setTo(nextTo);
            }}
          />
        </div>
        <div className="stat">
          <div className="label">Участники акции</div>
          <div className="value">
            <CountUp value={promoCount} />
          </div>
        </div>
        <div className="stat">
          <div className="label">Ср. % плана</div>
          <div className="value">
            <CountUp value={avgPercent} decimals={1} suffix="%" />
          </div>
        </div>
        <div className="stat">
          <div className="label">Рекомендации high</div>
          <div className="value">
            <CountUp value={highCount} />
          </div>
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
                <Tooltip cursor={false} formatter={(v: number) => formatMoney(v)} contentStyle={CHART_TOOLTIP} />
                <Bar dataKey="plan" fill="#0f766e" name="План" radius={[4, 4, 0, 0]} />
                <Bar dataKey="fact" fill="#c4a574" name="Факт" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {!chart.length && (
            <p className="empty">
              Нет квартальных планов — добавьте на экране <Link to="/quarterly">Квартальные отчеты</Link>.
            </p>
          )}
        </div>

        <div className="panel">
          <h2 style={{ marginTop: 0 }}>Тип работы</h2>
          <DashDonut data={workSlices} empty="Нет типов работы — заполните на экране Контрагенты." />
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2 style={{ marginTop: 0 }}>Залежалый товар</h2>
          {dwellSlices.length ? (
            <div style={{ width: "100%", height: 220 }}>
              <ResponsiveContainer>
                <BarChart data={dwellSlices}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.08)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip cursor={false} contentStyle={CHART_TOOLTIP} />
                  <Bar dataKey="value" name="Позиции" radius={[4, 4, 0, 0]}>
                    {dwellSlices.map((row) => (
                      <Cell key={row.name} fill={row.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="empty">Нет остатков для среза залежалого товара.</p>
          )}
        </div>

        <div className="panel">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
            <h2 style={{ margin: 0 }}>Рекомендации</h2>
            <Link className="muted" to="/recommendations">
              Все →
            </Link>
          </div>
          <DashDonut data={recSlices} empty={recsError || "Пока нет сигналов — нужны продажи/остатки и акционные клиенты."} />
        </div>
      </div>

      <div className="panel">
        <h2 style={{ marginTop: 0 }}>% выполнения плана</h2>
        {percentRows.length ? (
          <div style={{ width: "100%", height: Math.max(220, percentRows.length * 36) }}>
            <ResponsiveContainer>
              <BarChart data={percentRows} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.08)" />
                <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
                <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                <Tooltip cursor={false} formatter={(v: number) => `${Number(v).toFixed(1)}%`} contentStyle={CHART_TOOLTIP} />
                <Bar dataKey="percent" name="% плана" radius={[0, 4, 4, 0]}>
                  {percentRows.map((row) => (
                    <Cell key={row.name} fill={row.percent >= 100 ? "#0f766e" : "#dc2626"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="empty">Нет данных по плану</p>
        )}
      </div>

      <div className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Теплокарта залежалого товара</h2>
          <span className="muted">месяцы без продаж при наличии остатка</span>
        </div>
        <DwellHeatmap
          counterparties={heatmap?.counterparties || []}
          articles={heatmap?.articles || []}
          articleNames={heatmap?.article_names || {}}
          cells={heatmap?.cells || []}
          sourceLabel={labelOf}
        />
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
          {canSeeAdmin(me?.role) && (
            <Link className="btn secondary" to="/admin">
              Администрирование
            </Link>
          )}
        </div>
      </div>
    </>
  );
}
