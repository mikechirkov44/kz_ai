import { useState } from "react";
import { api, downloadFile, formatMoney } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";

type Row = {
  counterparty: string;
  counterparty_id: string;
  plan: number;
  fact: number;
  percent: number;
  dynamics?: number;
};

type SummaryDim = {
  dimension: string;
  avg_stock: number;
  sales_total: number;
  quarter_turnover_percent: number;
  avg_month_turnover_percent: number;
};

type SummaryClient = {
  counterparty: string;
  work_type?: string;
  work_type_percent?: number;
  sales_total: number;
  next_quarter_plan: number;
  blocks: Record<string, SummaryDim[]>;
};

export default function QuarterlyPage() {
  const [year, setYear] = useState(2023);
  const [quarter, setQuarter] = useState(1);
  const [rows, setRows] = useState<Row[]>([]);
  const [summary, setSummary] = useState<SummaryClient[]>([]);
  const [cpId, setCpId] = useState("");
  const [planValue, setPlanValue] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [plans, sum] = await Promise.all([
        api<{ clients: Row[] }>(`/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}`),
        api<{ clients: SummaryClient[] }>(
          `/api/v1/reports/quarterly-summary?year=${year}&quarter=${quarter}`,
        ),
      ]);
      setRows(plans.clients);
      setSummary(sum.clients);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }

  async function savePlan() {
    if (!cpId || !planValue) return;
    setMessage("");
    setError("");
    try {
      await api("/api/v1/reports/quarterly-plans", {
        method: "POST",
        body: JSON.stringify({
          year,
          quarter,
          counterparty_id: cpId,
          plan_value: planValue,
        }),
      });
      setMessage("План сохранён");
      setPlanValue("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function removePlan(counterpartyId: string) {
    setError("");
    try {
      await api(
        `/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}&counterparty_id=${counterpartyId}`,
        { method: "DELETE" },
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }

  return (
    <>
      <PageHeader
        title="Квартальные планы"
        subtitle="План/факт и итоговый отчёт §5.4 (Цвет металла / ЖЦТ / Тип изделия)"
        actions={
          <div className="toolbar">
            <button className="btn" onClick={load} disabled={loading}>
              {loading ? "Загрузка…" : "Обновить"}
            </button>
            <button
              className="btn secondary"
              onClick={() =>
                downloadFile(
                  `/api/v1/reports/quarterly-plans.xlsx?year=${year}&quarter=${quarter}`,
                  `quarterly_Q${quarter}_${year}.xlsx`,
                ).catch((err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"))
              }
            >
              Excel
            </button>
          </div>
        }
      />
      <div className="panel grid-3">
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
        <div className="field">
          <span>&nbsp;</span>
          <button className="btn secondary" onClick={load}>
            Показать отчёт
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Добавить / обновить план</h2>
        <CounterpartySelect value={cpId} onChange={setCpId} allowEmpty />
        <div className="grid-2" style={{ marginTop: 12 }}>
          <label className="field">
            <span>План, тг</span>
            <input
              value={planValue}
              onChange={(e) => setPlanValue(e.target.value)}
              placeholder="например 25000000"
            />
          </label>
          <div className="field">
            <span>&nbsp;</span>
            <button className="btn" onClick={savePlan} disabled={!cpId || !planValue}>
              Сохранить план
            </button>
          </div>
        </div>
        {message && <div className="alert ok" style={{ marginTop: 12 }}>{message}</div>}
        {error && <div className="alert" style={{ marginTop: 12 }}>{error}</div>}
      </div>

      <div className="panel">
        <h2>План / Факт</h2>
        <DataTable
          storageKey="quarterly-plans"
          rows={rows}
          rowKey={(r) => r.counterparty_id}
          empty="Планов пока нет"
          columns={[
            { key: "counterparty", title: "Контрагент", width: 220, sticky: true },
            {
              key: "plan",
              title: "План",
              width: 130,
              align: "right",
              render: (r) => formatMoney(r.plan),
            },
            {
              key: "fact",
              title: "Факт",
              width: 130,
              align: "right",
              render: (r) => formatMoney(r.fact),
            },
            {
              key: "percent",
              title: "% выполнения",
              width: 130,
              align: "right",
              render: (r) => formatMoney(r.percent),
            },
            {
              key: "dynamics",
              title: "Динамика",
              width: 110,
              getValue: (r) => r.dynamics ?? null,
              render: (r) => r.dynamics ?? "—",
            },
            {
              key: "actions",
              title: "",
              width: 110,
              sortable: false,
              render: (r) => (
                <button
                  className="btn danger sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    removePlan(r.counterparty_id);
                  }}
                >
                  Удалить
                </button>
              ),
            },
          ]}
        />
      </div>

      <div className="panel">
        <h2>Итоговый отчёт по кварталу (§5.4)</h2>
        <p className="muted">
          Средний остаток, продажи, об-ть квартала, ср. об-ть / 3 и план на следующий квартал по типу работы
        </p>
        {!summary.length && <p className="empty">Нет promo-клиентов с продажами/остатками за квартал</p>}
        {summary.map((client) => (
          <div key={client.counterparty} style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
              <h2 style={{ margin: 0, fontSize: "1.25rem" }}>{client.counterparty}</h2>
              <span className="pill">{client.work_type || "hold"}</span>
              <span className="pill gold">
                Продажи Q: {formatMoney(client.sales_total)} · План след.Q:{" "}
                {formatMoney(client.next_quarter_plan)}
              </span>
            </div>
            {Object.entries(client.blocks || {}).map(([blockName, dims]) => (
              <div key={blockName} style={{ marginBottom: 14 }}>
                <h3 style={{ margin: "0 0 8px", fontSize: "1rem" }}>{blockName}</h3>
                <DataTable
                  storageKey={`quarterly-block-${blockName}`}
                  maxHeight="320px"
                  rows={dims}
                  rowKey={(d) => d.dimension}
                  empty="Нет данных по блоку"
                  columns={[
                    { key: "dimension", title: blockName, width: 180, sticky: true },
                    {
                      key: "avg_stock",
                      title: "Ср. остаток",
                      width: 130,
                      align: "right",
                      render: (d) => formatMoney(d.avg_stock),
                    },
                    {
                      key: "sales_total",
                      title: "Продажи",
                      width: 130,
                      align: "right",
                      render: (d) => formatMoney(d.sales_total),
                    },
                    {
                      key: "quarter_turnover_percent",
                      title: "Об-ть квартала %",
                      width: 140,
                      align: "right",
                      render: (d) => formatMoney(d.quarter_turnover_percent),
                    },
                    {
                      key: "avg_month_turnover_percent",
                      title: "Ср. об-ть / 3 %",
                      width: 140,
                      align: "right",
                      render: (d) => formatMoney(d.avg_month_turnover_percent),
                    },
                  ]}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}
