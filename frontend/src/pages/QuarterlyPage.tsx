import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadFile, formatMoney } from "../api";
import CounterpartySelect from "../components/CounterpartySelect";
import DataTable from "../components/DataTable";
import FilePicker from "../components/FilePicker";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import QuarterlyMatrix, { type SummaryClient, type SummaryLabels } from "../components/QuarterlyMatrix";
import PeriodPicker from "../components/PeriodPicker";
import { currentQuarterRange, yearQuarterFromIso } from "../months";
import { QUARTERLY_TABS, shouldLoadQuarterlySummary, type QuarterlyTab } from "../quarterlyFilters";

type PlanRow = {
  counterparty: string;
  counterparty_id: string;
  plan: number;
  fact: number;
  percent: number;
  dynamics?: number;
  manager_name?: string | null;
  work_type?: string | null;
  work_type_label?: string | null;
  work_type_percent?: number | null;
};

type PlanSlice = {
  name: string;
  clients: number;
  fulfilled: number;
  percent: number;
};

type CommentRow = {
  id: string;
  text: string;
  created_at: string;
  author_name?: string | null;
};

export default function QuarterlyPage() {
  const initial = currentQuarterRange();
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const { year, quarter } = yearQuarterFromIso(from);
  const [tab, setTab] = useState<QuarterlyTab>("progress");
  const [rows, setRows] = useState<PlanRow[]>([]);
  const [slices, setSlices] = useState<PlanSlice[]>([]);
  const [summary, setSummary] = useState<SummaryClient[]>([]);
  const [labels, setLabels] = useState<SummaryLabels>({});
  const [cpId, setCpId] = useState("");
  const [planValue, setPlanValue] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [historyFor, setHistoryFor] = useState<string>("");
  const [history, setHistory] = useState<CommentRow[]>([]);
  const [planFile, setPlanFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  async function loadPlans() {
    setLoading(true);
    setError("");
    try {
      const plans = await api<{ clients: PlanRow[]; slices?: PlanSlice[] }>(
        `/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}`,
      );
      setRows(plans.clients);
      setSlices(plans.slices || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }

  async function loadSummary() {
    setSummaryLoading(true);
    try {
      const sum = await api<{ clients: SummaryClient[]; labels: SummaryLabels }>(
        `/api/v1/reports/quarterly-summary?year=${year}&quarter=${quarter}`,
      );
      setSummary(sum.clients);
      setLabels(sum.labels || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сводки");
    } finally {
      setSummaryLoading(false);
    }
  }

  function load() {
    void loadPlans();
    if (shouldLoadQuarterlySummary(tab)) void loadSummary();
  }

  useEffect(() => {
    void loadPlans();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, quarter]);

  useEffect(() => {
    if (!shouldLoadQuarterlySummary(tab)) return;
    void loadSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, year, quarter]);

  async function uploadPlans(e: FormEvent) {
    e.preventDefault();
    if (!planFile) return;
    setError("");
    setMessage("");
    setUploading(true);
    const body = new FormData();
    body.append("file", planFile);
    try {
      const result = await api<{ processed_rows: number; status: string }>(
        "/api/v1/uploads/quarterly-plans",
        { method: "POST", body },
      );
      setMessage(`Загружено планов: ${result.processed_rows}`);
      setPlanFile(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки плана");
    } finally {
      setUploading(false);
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
  const busy = loading || summaryLoading;

  return (
    <>
      <PageHeader title="Квартальные отчеты" subtitle="План, факт и итоговая матрица по клиентам" />
      <div className="panel filters-bar">
        <PeriodPicker
          from={from}
          to={to}
          mode="quarter"
          onChange={(nextFrom, nextTo) => {
            setFrom(nextFrom);
            setTo(nextTo);
            setSummary([]);
            setLabels({});
            setRows([]);
            setSlices([]);
          }}
        />
        <div className="filters-actions">
          <button className="btn" type="button" onClick={load} disabled={busy}>
            {busy ? "Считаем…" : "Показать"}
          </button>
          <button
            className="btn secondary"
            type="button"
            onClick={() =>
              downloadFile(
                `/api/v1/reports/quarterly-summary.xlsx?year=${year}&quarter=${quarter}`,
                `quarterly_summary_Q${quarter}_${year}.xlsx`,
              ).catch((err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"))
            }
          >
            Excel
          </button>
        </div>
      </div>
      <div className="seg-tabs" role="tablist" aria-label="Квартальные отчёты">
        {QUARTERLY_TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`seg-tab ${tab === item.id ? "active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {error && <div className="alert">{error}</div>}
      {message && tab === "plan" && <div className="alert ok">{message}</div>}

      {tab === "progress" && (
        <div className="panel">
          {!!slices.length && (
            <div className="stats" style={{ marginTop: 0, marginBottom: 16 }}>
              {slices.map((slice) => (
                <div className="stat" key={slice.name}>
                  <div className="label">{slice.name}</div>
                  <div className="value">{formatMoney(slice.percent)}%</div>
                  <div className="muted">
                    клиентов {slice.clients} · выполнен план {slice.fulfilled}
                  </div>
                </div>
              ))}
            </div>
          )}
          <DataTable
            storageKey="quarterly-plans"
            rows={rows}
            rowKey={(r) => r.counterparty_id}
            empty={loading ? "Считаем…" : "Планов пока нет"}
            columns={[
              { key: "counterparty", title: "Головной контрагент", width: 220, sticky: true },
              {
                key: "manager_name",
                title: "Менеджер",
                width: 160,
                getValue: (r) => r.manager_name || "",
                render: (r) => r.manager_name || "—",
              },
              {
                key: "work_type_label",
                title: "Тип работы",
                width: 140,
                getValue: (r) => r.work_type_label || r.work_type || "",
                render: (r) => r.work_type_label || r.work_type || "—",
              },
              {
                key: "work_type_percent",
                title: "% типа работы",
                width: 130,
                align: "right",
                getValue: (r) => r.work_type_percent ?? null,
                render: (r) => (r.work_type_percent != null ? formatMoney(r.work_type_percent) : "—"),
              },
              {
                key: "plan",
                title: "План на квартал",
                width: 140,
                align: "right",
                render: (r) => formatMoney(r.plan),
              },
              {
                key: "fact",
                title: "Факт квартал",
                width: 140,
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
      )}

      {tab === "summary" && (
        <div className="panel">
          <div className="toolbar" style={{ marginBottom: 12 }}>
            <Link className="btn secondary" to={`/quarterly/tz?year=${year}&quarter=${quarter}`} target="_blank" rel="noreferrer">
              Печать HTML
            </Link>
          </div>
          {summaryLoading && !summary.length ? (
            <p className="muted">Считаем сводку по клиентам…</p>
          ) : !summary.length ? (
            <p className="empty">Нет данных за этот квартал — загрузите продажи или нажмите «Показать».</p>
          ) : (
            <QuarterlyMatrix
              clients={summary}
              labels={labels}
              onSaveComment={saveComment}
              onShowHistory={(id) => {
                showHistory(id).catch((err) => setError(err instanceof Error ? err.message : "Ошибка истории"));
              }}
            />
          )}
        </div>
      )}

      {tab === "plan" && (
        <div className="panel">
          <h2>Загрузка из Excel</h2>
          <p className="muted">Колонки: Головной контрагент, Год, Квартал, Кол-во штук</p>
          <form className="toolbar" onSubmit={uploadPlans} style={{ marginTop: 8 }}>
            <FilePicker file={planFile} onChange={setPlanFile} />
            <button
              className="btn secondary"
              type="button"
              onClick={() =>
                downloadFile("/api/v1/uploads/templates/quarterly_plans", "template_quarterly_plans.xlsx").catch(
                  (err) => setError(err instanceof Error ? err.message : "Ошибка шаблона"),
                )
              }
            >
              Шаблон
            </button>
            <button className="btn" type="submit" disabled={!planFile || uploading}>
              {uploading ? "Загружаем…" : "Загрузить Excel"}
            </button>
          </form>
          <h2 style={{ marginTop: 24 }}>Добавить / обновить план</h2>
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
        </div>
      )}

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
