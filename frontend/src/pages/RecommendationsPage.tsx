import { useEffect, useState } from "react";
import { api } from "../api";
import AiBriefing from "../components/AiBriefing";
import PageHeader from "../components/PageHeader";
import RecommendationCard from "../components/RecommendationCard";
import {
  REC_ACTION_TABS,
  filterRecommendations,
  type RecAction,
  type Recommendation,
} from "../recommendations";

type Report = {
  items: Recommendation[];
  llm_status?: string;
  summary?: string;
};

export default function RecommendationsPage() {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [summary, setSummary] = useState("");
  const [llmStatus, setLlmStatus] = useState("off");
  const [tab, setTab] = useState<"all" | RecAction>("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api<Report>("/api/v1/reports/recommendations");
      setItems(data.items || []);
      setSummary(data.summary || "");
      setLlmStatus(data.llm_status || "off");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const visible = filterRecommendations(items, tab);

  return (
    <>
      <PageHeader
        title="Рекомендации"
        subtitle="Ассистент разбирает залежалый товар, перекос ассортимента и цены отгрузки"
        actions={
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Считаю…" : "Обновить"}
          </button>
        }
      />
      {error && <div className="alert">{error}</div>}
      <AiBriefing
        summary={llmStatus === "ok" ? summary : ""}
        llmStatus={llmStatus}
        thinking={loading && !items.length}
        count={items.length}
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
      <div className="rec-list">
        {visible.map((item, idx) => (
          <RecommendationCard key={`${item.type}-${item.article || idx}-${item.counterparty || idx}`} item={item} delay={idx * 40} />
        ))}
      </div>
    </>
  );
}
