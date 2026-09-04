import { useEffect, useState } from "react";
import { api } from "../api";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";

type AuditItem = {
  id: string;
  user_email?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  details?: Record<string, unknown> | null;
  created_at: string;
};

export default function AuditPage() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<AuditItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  async function load(p = 1) {
    setError("");
    const sp = new URLSearchParams({ page: String(p), page_size: "50" });
    if (q.trim()) sp.set("q", q.trim());
    try {
      const data = await api<{ items: AuditItem[]; total: number }>(`/api/v1/audit?${sp}`);
      setItems(data.items);
      setTotal(data.total);
      setPage(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить журнал");
    }
  }

  useEffect(() => {
    const t = setTimeout(() => load(1).catch(() => undefined), 200);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <>
      <PageHeader title="Журнал аудита" subtitle="Кто что сделал: вход, синхронизация, загрузки, отчёты, пользователи" />
      {error && <div className="alert">{error}</div>}
      <div className="panel">
        <label className="field">
          <span>Поиск по действию</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="login, sync, upload…" />
        </label>
      </div>
      <p className="muted">Всего: {total}</p>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey="audit"
          rows={items}
          rowKey={(r) => r.id}
          columns={[
            {
              key: "created_at",
              title: "Время",
              width: 170,
              getValue: (r) => r.created_at,
              render: (r) => new Date(r.created_at).toLocaleString("ru-RU"),
            },
            {
              key: "user_email",
              title: "Пользователь",
              width: 200,
              getValue: (r) => r.user_email || "",
              render: (r) => r.user_email || "—",
            },
            { key: "action", title: "Действие", width: 180 },
            {
              key: "entity_type",
              title: "Сущность",
              width: 140,
              getValue: (r) => r.entity_type || "",
              render: (r) => r.entity_type || "—",
            },
            {
              key: "details",
              title: "Детали",
              width: 280,
              sortable: false,
              getValue: (r) => JSON.stringify(r.details || {}),
              render: (r) => (
                <span className="muted" title={JSON.stringify(r.details || {})}>
                  {r.details ? JSON.stringify(r.details) : "—"}
                </span>
              ),
            },
          ]}
        />
      </div>
      <div className="toolbar">
        <button className="btn secondary" disabled={page <= 1} onClick={() => load(page - 1)}>
          ←
        </button>
        <span className="pill">стр. {page}</span>
        <button className="btn secondary" disabled={items.length < 50} onClick={() => load(page + 1)}>
          →
        </button>
      </div>
    </>
  );
}
