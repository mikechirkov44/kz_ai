import { useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadFile, formatMoney } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import QuarterlyMatrix, { type SummaryClient, type SummaryLabels } from "../components/QuarterlyMatrix";
import PeriodPicker from "../components/PeriodPicker";
import { quarterRange, yearQuarterFromIso } from "../months";

type PlanRow = {
  counterparty: string;
  counterparty_id: string;
  plan: number;
  fact: number;
  percent: number;
  dynamics?: number;
};

type CommentRow = {
  id: string;
  text: string;
  created_at: string;
  author_name?: string | null;
};

export default function QuarterlyPage() {
  const [from, setFrom] = useState(quarterRange(2023, 1).from);
  const [to, setTo] = useState(quarterRange(2023, 1).to);
  const { year, quarter } = yearQuarterFromIso(from);
  const [rows, setRows] = useState<PlanRow[]>([]);
  const [summary, setSummary] = useState<SummaryClient[]>([]);
  const [labels, setLabels] = useState<SummaryLabels>({});
  const [cpId, setCpId] = useState("");
  const [planValue, setPlanValue] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyFor, setHistoryFor] = useState<string>("");
  const [history, setHistory] = useState<CommentRow[]>([]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [plans, sum] = await Promise.all([
        api<{ clients: PlanRow[] }>(`/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}`),
        api<{ clients: SummaryClient[]; labels: SummaryLabels }>(
          `/api/v1/reports/quarterly-summary?year=${year}&quarter=${quarter}`,
        ),
      ]);
      setRows(plans.clients);
      setSummary(sum.clients);
      setLabels(sum.labels || {});
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

  async function saveComment(counterpartyId: string, text: string) {
    setError("");
    await api("/api/v1/reports/quarterly-comments", {
      method: "POST",
      body: JSON.stringify({ year, quarter, counterparty_id: counterpartyId, text }),
    });
    await load();
  }

  async function showHistory(counterpartyId: string) {
    setError("");
    const rowsHist = await api<CommentRow[]>(
      `/api/v1/reports/quarterly-comments?year=${year}&quarter=${quarter}&counterparty_id=${counterpartyId}`,
    );
    setHistory(rowsHist);
    setHistoryFor(counterpartyId);
  }

  const historyName = summary.find((c) => c.counterparty_id === historyFor)?.counterparty || "";

  return (
    <>
      <PageHeader
        title="Квартальные планы"
        subtitle="План, факт и итоги по клиентам"
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
                  `quarterly_plans_Q${quarter}_${year}.xlsx`,
                ).catch((err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"))
              }
            >
              Excel план/факт
            </button>
            <button
              className="btn secondary"
              onClick={() =>
                downloadFile(
                  `/api/v1/reports/quarterly-summary.xlsx?year=${year}&quarter=${quarter}`,
                  `quarterly_summary_Q${quarter}_${year}.xlsx`,
                ).catch((err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"))
              }
            >
              Excel отчёта
            </button>
            <Link className="btn secondary" to={`/quarterly/tz?year=${year}&quarter=${quarter}`} target="_blank" rel="noreferrer">
              Открыть таблицу
            </Link>
          </div>
        }
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
        <div className="field">
          <span>&nbsp;</span>
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Загрузка…" : "Показать отчёт"}
          </button>
        </div>
      </div>

      <details className="panel">
        <summary>
          <strong>План / факт</strong>
          <span className="muted"> — план и выполнение</span>
        </summary>
        <div style={{ marginTop: 12 }}>
          <h3>Добавить / обновить план</h3>
          <CounterpartySelect value={cpId} onChange={setCpId} allowEmpty compact />
          <div className="grid-2" style={{ marginTop: 12 }}>
            <label className="field">
              <span>План, шт</span>
              <input
                value={planValue}
                onChange={(e) => setPlanValue(e.target.value)}
                placeholder="например 50"
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
        </div>
        <h3>Промежуточные итоги</h3>
        <DataTable
          storageKey="quarterly-plans"
          rows={rows}
          rowKey={(r) => r.counterparty_id}
          empty="Планов пока нет"
          columns={[
            { key: "counterparty", title: "Контрагент", width: 220, sticky: true },
            {
              key: "plan",
              title: "План, шт",
              width: 130,
              align: "right",
              render: (r) => formatMoney(r.plan),
            },
            {
              key: "fact",
              title: "Факт, шт",
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
      </details>
      {error && <div className="alert">{error}</div>}

      <div className="panel">
        <h2>Итоговый отчёт по кварталу</h2>
        <QuarterlyMatrix
          clients={summary}
          labels={labels}
          onSaveComment={saveComment}
          onShowHistory={(id) => {
            showHistory(id).catch((err) => setError(err instanceof Error ? err.message : "Ошибка истории"));
          }}
        />
      </div>

      <Modal
        open={Boolean(historyFor)}
        title={`Комментарии: ${historyName}`}
        subtitle="История комментариев"
        onClose={() => setHistoryFor("")}
      >
        {!history.length && <p className="empty">Комментариев ещё нет</p>}
        {history.map((item) => (
          <div key={item.id} className="dash-rec-item" style={{ marginBottom: 8 }}>
            <div className="muted">
              {item.author_name || "—"} · {new Date(item.created_at).toLocaleString("ru-RU")}
            </div>
            <div>{item.text}</div>
          </div>
        ))}
      </Modal>
    </>
  );
}
