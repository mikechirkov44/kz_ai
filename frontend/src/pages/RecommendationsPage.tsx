import { useEffect, useState } from "react";
import { api } from "../api";
import PageHeader from "../components/PageHeader";

type Item = {
  type: string;
  severity: string;
  counterparty?: string;
  article?: string;
  message: string;
};

export default function RecommendationsPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api<{ items: Item[] }>("/api/v1/reports/recommendations");
      setItems(data.items);
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
        subtitle="Rule-based: неликвиды, успешные паттерны и ценовой арбитраж"
        actions={
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Считаем…" : "Обновить"}
          </button>
        }
      />
      {error && <div className="alert">{error}</div>}
      {!items.length && !error && !loading && (
        <div className="panel empty">Нет рекомендаций — нужны акционные клиенты и продажи/остатки Excel.</div>
      )}
      {loading && !items.length && <p className="muted">Загрузка…</p>}
      {items.map((item, idx) => (
        <div key={idx} className={`panel rec-card ${item.severity}`} style={{ animationDelay: `${idx * 40}ms` }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
            <span className="pill">{item.type}</span>
            <span className={`pill ${item.severity === "high" ? "bad" : item.severity === "medium" ? "warn" : "ok"}`}>
              {item.severity}
            </span>
          </div>
          {(item.counterparty || item.article) && (
            <div className="muted" style={{ marginBottom: 6 }}>
              {item.counterparty}
              {item.article ? ` · ${item.article}` : ""}
            </div>
          )}
          <p style={{ margin: 0 }}>{item.message}</p>
        </div>
      ))}
    </>
  );
}
