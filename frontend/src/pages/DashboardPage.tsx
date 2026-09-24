import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, canSeeAdmin, formatMoney, listCounterparties } from "../api";
import { useAuth } from "../auth";
import ChartWait from "../components/ChartWait";
import CountUp from "../components/CountUp";
import CbrRates, { type CbrRatesResponse } from "../components/CbrRates";
import DashDonut from "../components/DashDonut";
import DwellHeatmap from "../components/DwellHeatmap";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import QuickStart from "../components/QuickStart";
import SystemHealth from "../components/SystemHealth";
import type { SystemHealthPayload } from "../systemHealth";
import {
  currentWeeklyBar,
  planPercentChart,
  recSeverityChart,
  topSalesByCounterparty,
  topSalesByManager,
  weeklyPlanChart,
  workTypeChart,
  type SalesBar,
  type SalesClient,
  type WeeklyWeek,
} from "../dashboardCharts";
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

type Weekly = {
  year: number;
  quarter: number;
  plan_total: number;
  weeks: WeeklyWeek[];
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
  const isAdmin = canSeeAdmin(me?.role);
  const { labelOf } = useODataSources();
  const [data, setData] = useState<Quarterly | null>(null);
  const [plansLoading, setPlansLoading] = useState(true);
  const [promoCount, setPromoCount] = useState(0);
  const [promoLoading, setPromoLoading] = useState(true);
  const [recs, setRecs] = useState<RecItem[]>([]);
  const [recsError, setRecsError] = useState("");
  const [recsLoading, setRecsLoading] = useState(true);
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [cbr, setCbr] = useState<CbrRatesResponse | null>(null);
  const [salesClients, setSalesClients] = useState<SalesClient[]>([]);
  const [salesLoading, setSalesLoading] = useState(true);
  const [weekly, setWeekly] = useState<Weekly | null>(null);
  const [weeklyLoading, setWeeklyLoading] = useState(true);
  const [health, setHealth] = useState<SystemHealthPayload | null>(null);
  const [healthError, setHealthError] = useState("");

  useEffect(() => {
    setPlansLoading(true);
    setWeeklyLoading(true);
    setSalesLoading(true);
    api<Quarterly>(`/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}`)
      .then(setData)
      .catch(() => setData({ year, quarter, clients: [] }))
      .finally(() => setPlansLoading(false));
    api<Weekly>(`/api/v1/reports/quarterly-weekly?year=${year}&quarter=${quarter}`)
      .then(setWeekly)
      .catch(() => setWeekly({ year, quarter, plan_total: 0, weeks: [] }))
      .finally(() => setWeeklyLoading(false));
    api<{ clients: SalesClient[] }>(`/api/v1/reports/quarterly-results?year=${year}&quarter=${quarter}`)
      .then((payload) => setSalesClients(payload.clients || []))
      .catch(() => setSalesClients([]))
      .finally(() => setSalesLoading(false));
  }, [quarter, year]);

  useEffect(() => {
    listCounterparties({ promo_only: true })
      .then((rows) => setPromoCount(rows.length))
      .catch(() => setPromoCount(0))
      .finally(() => setPromoLoading(false));
    api<{ items: RecItem[] }>("/api/v1/reports/recommendations")
      .then((r) => setRecs(r.items || []))
      .catch((err) => setRecsError(err instanceof Error ? err.message : "Нет рекомендаций"))
      .finally(() => setRecsLoading(false));
    api<Heatmap>("/api/v1/reports/dwell-heatmap")
      .then(setHeatmap)
      .catch(() => setHeatmap({ counterparties: [], articles: [], cells: [] }))
      .finally(() => setHeatmapLoading(false));
    api<CbrRatesResponse>("/api/v1/reports/cbr-rates")
      .then(setCbr)
      .catch(() => setCbr({ status: "error", items: [] }));
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      setHealth(null);
      setHealthError("");
      return;
    }
    api<SystemHealthPayload>("/api/v1/health")
      .then((payload) => {
        setHealth(payload);
        setHealthError("");
      })
      .catch((err) => {
        setHealth(null);
        setHealthError(err instanceof Error ? err.message : "Нет связи с API");
      });
  }, [isAdmin]);

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
  const recSlices = recSeverityChart(recs);
  const percentRows = planPercentChart(
    clients.map((c) => ({ counterparty: c.counterparty, percent: Number(c.percent) })),
  );
  const topClients = topSalesByCounterparty(salesClients);
  const topManagers = topSalesByManager(salesClients);
  const weeklyChart = weeklyPlanChart(weekly?.weeks || []);
  const thisWeek = currentWeeklyBar(weeklyChart);

  return (
    <>
      <PageHeader
        title="Дашборд"
        subtitle="Сводка по выбранному кварталу и рекомендациям"
        actions={
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
        }
      />

      <CbrRates data={cbr} />

      <div className="stats stats-3">
        <div className="stat">
          <div className="label">Участники акции</div>
          <div className="value">
            {promoLoading ? <span className="chart-wait-value" aria-label="Считаю участников" /> : <CountUp value={promoCount} />}
          </div>
        </div>
        <div className="stat">
          <div className="label">Ср. % плана</div>
          <div className="value">
            {plansLoading ? <span className="chart-wait-value" aria-label="Считаю средний процент" /> : <CountUp value={avgPercent} decimals={1} suffix="%" />}
          </div>
        </div>
        <div className="stat">
          <div className="label">Срочные рекомендации</div>
          <div className="value">
            {recsLoading ? <span className="chart-wait-value" aria-label="Считаю срочные рекомендации" /> : <CountUp value={highCount} />}
          </div>
        </div>
      </div>

      {isAdmin ? <SystemHealth variant="strip" health={health} error={healthError} /> : null}

      {me?.id && <QuickStart userId={me.id} role={me.role} />}

      <div className="panel">
        <PanelHead title="План / факт по неделям" source="1С" to="/quarterly" />
        <p className="muted" style={{ margin: "0 0 12px" }}>
          Квартальный план делится по дням (пн–вс). Факт — отгрузки 1С клиентов с планом. План в штуках, факт в тенге;
          смотрите процент.
        </p>
        {thisWeek && (
          <p style={{ margin: "0 0 12px" }}>
            Эта неделя ({thisWeek.label}): план {formatMoney(thisWeek.plan)} · факт {formatMoney(thisWeek.fact)} ·{" "}
            {thisWeek.percent.toFixed(1)}%
          </p>
        )}
        {weeklyLoading ? (
          <ChartWait label="Считаю план и факт по неделям" />
        ) : weeklyChart.length ? (
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={weeklyChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.08)" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  cursor={false}
                  formatter={(v: number) => formatMoney(v)}
                  labelFormatter={(_label, payload) => (payload?.[0]?.payload as { label?: string } | undefined)?.label || ""}
                  contentStyle={CHART_TOOLTIP}
                />
                <Legend
                  payload={[
                    { value: "План", type: "square", color: "#0f766e" },
                    { value: "Факт", type: "square", color: "#c4a574" },
                  ]}
                />
                <Bar dataKey="plan" fill="#0f766e" name="План" radius={[4, 4, 0, 0]}>
                  {weeklyChart.map((row) => (
                    <Cell key={`plan-${row.name}`} fill={row.isCurrent ? "#115e59" : "#0f766e"} />
                  ))}
                </Bar>
                <Bar dataKey="fact" fill="#c4a574" name="Факт" radius={[4, 4, 0, 0]}>
                  {weeklyChart.map((row) => (
                    <Cell key={`fact-${row.name}`} fill={row.isCurrent ? "#a07848" : "#c4a574"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="empty">
            Нет квартальных планов — добавьте на экране <Link to="/quarterly">Квартальные отчеты</Link>.
          </p>
        )}
      </div>

      <div className="grid-2">
        <div className="panel">
          <PanelHead title="План / факт по клиентам" source="1С" to="/quarterly" />
          {plansLoading ? (
            <ChartWait label="Собираю план и факт по клиентам" />
          ) : chart.length ? (
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
          ) : (
            <p className="empty">
              Нет квартальных планов — добавьте на экране <Link to="/quarterly">Квартальные отчеты</Link>.
            </p>
          )}
        </div>

        <div className="panel">
          <PanelHead title="Тип работы" />
          {plansLoading ? (
            <ChartWait label="Считаю типы работы" />
          ) : (
            <DashDonut data={workSlices} empty="Нет типов работы — заполните на экране Контрагенты." />
          )}
        </div>
      </div>

      <div className="grid-2">
        <TopSalesPanel
          title="ТОП-5 контрагентов"
          rows={topClients}
          loading={salesLoading}
          loadingLabel="Считаю продажи контрагентов"
          empty="Нет Excel-продаж за квартал у акционных клиентов."
        />
        <TopSalesPanel
          title="ТОП-5 менеджеров"
          rows={topManagers}
          loading={salesLoading}
          loadingLabel="Считаю продажи менеджеров"
          empty="Нет Excel-продаж за квартал у акционных клиентов."
        />
      </div>

      <div className="grid-2">
        <div className="panel">
          <PanelHead title="Рекомендации" to="/recommendations" linkLabel="Все →" />
          {recsLoading ? (
            <ChartWait label="Собираю рекомендации" />
          ) : (
            <DashDonut data={recSlices} empty={recsError || "Пока нет сигналов — нужны продажи/остатки и акционные клиенты."} />
          )}
        </div>

        <div className="panel">
          <PanelHead title="Отстающие по плану" source="1С" extra={<span className="muted">&lt; 100%, до 12</span>} />
          {plansLoading ? (
            <ChartWait label="Ищу отстающих по плану" />
          ) : percentRows.length ? (
            <div style={{ width: "100%", height: Math.max(220, percentRows.length * 36) }}>
              <ResponsiveContainer>
                <BarChart data={percentRows} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.08)" />
                  <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
                  <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                  <Tooltip cursor={false} formatter={(v: number) => `${Number(v).toFixed(1)}%`} contentStyle={CHART_TOOLTIP} />
                  <Bar dataKey="percent" name="% плана" fill="#dc2626" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="empty">{clients.length ? "Отстающих нет" : "Нет данных по плану"}</p>
          )}
        </div>
      </div>

      <div className="panel">
        <PanelHead
          title="Теплокарта залежалого товара"
          source="Excel"
          extra={<span className="muted">месяцы без продаж при наличии остатка</span>}
        />
        {heatmapLoading ? (
          <ChartWait label="Строю теплокарту залежалого товара" />
        ) : (
          <DwellHeatmap
            counterparties={heatmap?.counterparties || []}
            articles={heatmap?.articles || []}
            articleNames={heatmap?.article_names || {}}
            cells={heatmap?.cells || []}
            sourceLabel={labelOf}
          />
        )}
      </div>
    </>
  );
}

function PanelHead({
  title,
  to,
  source,
  extra,
  linkLabel = "Открыть →",
}: {
  title: string;
  to?: string;
  source?: string;
  extra?: ReactNode;
  linkLabel?: string;
}) {
  return (
    <div className="panel-head">
      <h2>{title}</h2>
      <div className="panel-head-meta">
        {source ? <span className="panel-source">{source}</span> : null}
        {extra}
        {to ? (
          <Link className="muted" to={to}>
            {linkLabel}
          </Link>
        ) : null}
      </div>
    </div>
  );
}

function TopSalesPanel({
  title,
  rows,
  empty,
  loading = false,
  loadingLabel = "",
}: {
  title: string;
  rows: SalesBar[];
  empty: string;
  loading?: boolean;
  loadingLabel?: string;
}) {
  return (
    <div className="panel">
      <PanelHead title={title} source="Excel" to="/quarterly" />
      {loading ? (
        <ChartWait label={loadingLabel} />
      ) : rows.length ? (
        <div style={{ width: "100%", height: Math.max(200, rows.length * 42) }}>
          <ResponsiveContainer>
            <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.08)" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 11 }} />
              <Tooltip
                cursor={false}
                formatter={(value: number) => formatMoney(value)}
                contentStyle={CHART_TOOLTIP}
              />
              <Bar dataKey="sales" name="Продажи" fill="#0f766e" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="empty">{empty}</p>
      )}
    </div>
  );
}
