import { useState } from "react";
import { api } from "../api";

type Item = { type: string; severity: string; counterparty?: string; article?: string; message: string };

export default function RecommendationsPage() {
  const [items, setItems] = useState<Item[]>([]);

  async function load() {
    const data = await api<{ items: Item[] }>("/api/v1/reports/recommendations");
    setItems(data.items);
  }

  return (
    <>
      <h1>AI-рекомендации</h1>
      <p className="muted">Rule-Based: неликвиды, успешные паттерны, ценовой арбитраж</p>
      <div className="panel">
        <button className="btn" onClick={load}>Сгенерировать</button>
      </div>
      {items.map((item, idx) => (
        <div key={idx} className="panel" style={{ borderLeft: `4px solid ${item.severity === "high" ? "var(--bad)" : item.severity === "medium" ? "var(--warn)" : "var(--brand)"}` }}>
          <div className="pill">{item.type}</div>
          {item.counterparty && <div className="muted">{item.counterparty}{item.article ? ` · ${item.article}` : ""}</div>}
          <p>{item.message}</p>
        </div>
      ))}
    </>
  );
}
