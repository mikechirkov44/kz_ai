import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import AiBriefing from "../components/AiBriefing";
import ExecutiveReport from "../components/ExecutiveReport";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import RecommendationCard from "../components/RecommendationCard";
import {
  REC_ACTION_TABS,
  filterRecommendations,
  groupActionSummary,
  groupRecommendations,
  type RecAction,
  type Recommendation,
} from "../recommendations";
import type { LlmReport } from "../components/ExecutiveReport";

type Report = {
  generated_at?: string;
  items: Recommendation[];
  llm_status?: string;
  summary?: string;
  llm_report?: LlmReport | null;
};

export default function RecommendationsPage() {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [summary, setSummary] = useState("");
  const [llmStatus, setLlmStatus] = useState("off");
  const [tab, setTab] = useState<"all" | RecAction>("all");
  const [loading, setLoading] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [error, setError] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const [llmReport, setLlmReport] = useState<LlmReport | null>(null);
  const [openClients, setOpenClients] = useState<string[]>([]);
  const loadSeq = useRef(0);

  async function load() {
    const seq = ++loadSeq.current;
    setLoading(true);
    setEnriching(false);
    setError("");
    try {
      const data = await api<Report>("/api/v1/reports/recommendations");
      if (seq !== loadSeq.current) return;
      setItems(data.items || []);
      setSummary(data.summary || "");
      setLlmStatus(data.llm_status || "off");
      setLlmReport(null);
      setOpenClients([]);
      setLoading(false);
      if (!data.items?.length) return;
      setEnriching(true);
      try {
        const enriched = await api<Report>("/api/v1/reports/recommendations/enrich", {
          method: "POST",
          body: JSON.stringify(data),
        });
        if (seq !== loadSeq.current) return;
        setItems(enriched.items || data.items);
        setSummary(enriched.summary || data.summary);
        setLlmStatus(enriched.llm_status || data.llm_status);
        setLlmReport(enriched.llm_report || null);
      } catch {
        /* правила уже на экране */
      }
    } catch (err) {
      if (seq !== loadSeq.current) return;
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      if (seq === loadSeq.current) {
        setLoading(false);
        setEnriching(false);
      }
    }
  }

  useEffect(() => {
    load();
  }, []);

  const visible = filterRecommendations(items, tab);
  const groups = groupRecommendations(visible);

  return (
    <div className={`rec-page ${llmStatus === "ok" ? "rec-page-llm" : ""}`}>
      <PageHeader
        title="Рекомендации"
        subtitle="Залежалый товар, подсортировка, перекладка и цены"
        actions={
          <button className="btn" onClick={load} disabled={loading || enriching}>
            {loading ? "Анализирую…" : enriching ? "Дописываю советы…" : "Обновить"}
          </button>
        }
      />
      {error && <div className="alert">{error}</div>}
      <AiBriefing
        summary={summary}
        llmStatus={llmStatus}
        thinking={loading && !items.length}
        enriching={enriching}
        count={items.length}
        items={items}
        onOpenReport={() => setReportOpen(true)}
      />
      <div className="seg-tabs" role="tablist" aria-label="Тип рекомендации">
        {REC_ACTION_TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`seg-tab ${tab === item.id ? "active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
            {item.id !== "all" && (
              <span className="seg-count">{filterRecommendations(items, item.id).length}</span>
            )}
          </button>
        ))}
      </div>
      {!visible.length && !error && !loading && (
        <div className="panel empty">
          {items.length
            ? "В этом срезе сигналов нет — переключите вкладку."
            : "Нет рекомендаций — загрузите продажи и остатки клиентов."}
        </div>
      )}
      {groups.length ? (
        <div className="rec-fold-bar">
          <button type="button" className="btn ghost sm" onClick={() => setOpenClients(groups.map((g) => g.counterparty))}>
            Развернуть все
          </button>
          <button type="button" className="btn ghost sm" onClick={() => setOpenClients([])}>
            Свернуть все
          </button>
        </div>
      ) : null}
      <div className="rec-list">
        {groups.map((group) => {
          const open = openClients.includes(group.counterparty);
          return (
            <section key={group.counterparty} className={`rec-group ${open ? "is-open" : "is-collapsed"}`}>
              <button
                type="button"
                className="rec-group-head rec-group-toggle"
                aria-expanded={open}
                onClick={() =>
                  setOpenClients((prev) =>
                    prev.includes(group.counterparty)
                      ? prev.filter((name) => name !== group.counterparty)
                      : [...prev, group.counterparty],
                  )
                }
              >
                <span className="rec-group-caret" aria-hidden="true">
                  {open ? "▾" : "▸"}
                </span>
                <h2>{group.counterparty}</h2>
                <span className="muted">{groupActionSummary(group.items) || `${group.items.length}`}</span>
                <span className="rec-group-count">{group.items.length}</span>
              </button>
              {open
                ? group.items.map((item, idx) => (
                    <RecommendationCard
                      key={`${item.type}-${item.article || idx}-${item.title || idx}`}
                      item={item}
                      hideClient
                      delay={idx * 40}
                    />
                  ))
                : null}
            </section>
          );
        })}
      </div>
      <Modal
        open={reportOpen}
        wide
        title="Аналитический отчёт"
        subtitle="Сводка для руководителя по акционным клиентам"
        onClose={() => setReportOpen(false)}
      >
        <ExecutiveReport summary={summary} items={items} llmReport={llmReport} />
      </Modal>
    </div>
  );
}
