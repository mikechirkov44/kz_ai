import { useEffect, useState } from "react";
import { api } from "../api";
import PageHeader from "../components/PageHeader";

type Item = {
  type: string;
  severity: string;
  counterparty?: string;
  article?: string;
  message: string;
  llm_comment?: string | null;
};

export default function RecommendationsPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [llmStatus, setLlmStatus] = useState("off");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api<{ items: Item[]; llm_status?: string }>("/api/v1/reports/recommendations");
      setItems(data.items);
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

  return (
    <>
      <PageHeader
        title="Рекомендации"
        subtitle="Неликвиды, паттерны продаж и цены отгрузки. ИИ добавляет совет, если подключён в админке."
        actions={
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Считаем…" : "Обновить"}
          </button>
        }
      />
      {error && <div className="alert">{error}</div>}
      {llmStatus === "ok" && <p className="muted">Обогащено LLM</p>}
      {llmStatus === "error" && (
        <p className="muted">ИИ-обогащение недоступно — показаны только правила.</p>
      )}
      {!items.length && !error && !loading && (
        <div className="panel empty">Нет рекомендаций — загрузите продажи и остатки клиентов.</div>
      )}
      {loading && !items.length && <p className="muted">Загрузка…</p>}
      {items.map((item, idx) => (
        <div key={idx} className={`panel rec-card ${item.severity}`} style={{ animationDelay: `${idx * 40}ms` }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
            <span className="pill">{item.type}</span>
            <span className={`pill ${item.severity === "high" ? "bad" : item.severity === "medium" ? "warn" : "ok"}`}>
              {item.severity}
            </span>
            {item.llm_comment && <span className="pill">ИИ</span>}
          </div>
          {(item.counterparty || item.article) && (
            <div className="muted" style={{ marginBottom: 6 }}>
              {item.counterparty}
              {item.article ? ` · ${item.article}` : ""}
            </div>
          )}
          <p style={{ margin: 0 }}>{item.message}</p>
          {item.llm_comment && (
            <div className="rec-llm">
              <div className="rec-llm-label">Совет ИИ</div>
              {item.llm_comment}
            </div>
          )}
        </div>
      ))}
    </>
  );
}
