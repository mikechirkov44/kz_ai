import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Counterparty, listCounterparties } from "../api";
import DataTable from "../components/DataTable";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";

type Sync = {
  source_id: string;
  entity: string;
  status: string;
  rows_synced: number;
  last_error?: string;
  last_incremental_at?: string;
};

type Health = { status: string; database: string; redis: string; odata: Record<string, string> };

type ODataConn = {
  source_id: string;
  label: string;
  base_url: string;
  username: string;
  password_set: boolean;
  verify_ssl: boolean;
  enabled: boolean;
};

type ConnDraft = ODataConn & { password: string };

export default function AdminPage() {
  const [sync, setSync] = useState<Sync[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [message, setMessage] = useState("");
  const [sourceId, setSourceId] = useState("asil");
  const [cps, setCps] = useState<Counterparty[]>([]);
  const [cpQ, setCpQ] = useState("");
  const [promoOnly, setPromoOnly] = useState(false);
  const [digestYear, setDigestYear] = useState(new Date().getFullYear());
  const [digestQuarter, setDigestQuarter] = useState(Math.floor(new Date().getMonth() / 3) + 1);
  const [digestPreview, setDigestPreview] = useState("");
  const [connections, setConnections] = useState<ConnDraft[]>([]);
  const [connMsg, setConnMsg] = useState("");

  async function refresh() {
    setHealth(await api<Health>("/api/v1/health"));
    try {
      setSync(await api<Sync[]>("/api/v1/sync/status"));
    } catch {
      setSync([]);
    }
  }

  async function loadConnections() {
    try {
      const rows = await api<ODataConn[]>("/api/v1/odata/connections");
      setConnections(rows.map((r) => ({ ...r, password: "" })));
      setConnMsg("");
    } catch (err) {
      setConnections([]);
      setConnMsg(err instanceof Error ? err.message : "Не удалось загрузить подключения 1С");
    }
  }

  async function loadCounterparties() {
    const rows = await listCounterparties({
      promo_only: promoOnly,
      source_id: sourceId || undefined,
      q: cpQ || undefined,
    });
    setCps(rows);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
    loadConnections().catch(() => setConnections([]));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      loadCounterparties().catch(() => setCps([]));
    }, 200);
    return () => clearTimeout(t);
  }, [cpQ, promoOnly, sourceId]);

  function updateDraft(source_id: string, patch: Partial<ConnDraft>) {
    setConnections((prev) => prev.map((c) => (c.source_id === source_id ? { ...c, ...patch } : c)));
  }

  async function saveConnection(c: ConnDraft) {
    setConnMsg("");
    try {
      const body: Record<string, unknown> = {
        base_url: c.base_url,
        username: c.username,
        verify_ssl: c.verify_ssl,
        enabled: c.enabled,
        label: c.label,
      };
      if (c.password) body.password = c.password;
      const saved = await api<ODataConn>(`/api/v1/odata/connections/${c.source_id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      updateDraft(c.source_id, { ...saved, password: "" });
      setConnMsg(`Сохранено: ${c.source_id}`);
      await refresh();
    } catch (err) {
      setConnMsg(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function testConnection(source_id: string) {
    setConnMsg("Проверка…");
    try {
      const res = await api<{ status: string }>(`/api/v1/odata/connections/${source_id}/test`, {
        method: "POST",
      });
      setConnMsg(`${source_id}: ${res.status}`);
      await refresh();
    } catch (err) {
      setConnMsg(err instanceof Error ? err.message : "Ошибка проверки");
    }
  }

  async function runSync(full: boolean, background = false) {
    setMessage(background ? "Ставим в очередь…" : "Синхронизация…");
    try {
      const params = new URLSearchParams({
        full: String(full),
        background: String(background),
      });
      if (sourceId) params.set("source_id", sourceId);
      const result = await api<Record<string, unknown>>(`/api/v1/sync/run?${params}`, {
        method: "POST",
      });
      setMessage(JSON.stringify(result, null, 2));
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка синка");
    }
  }

  async function togglePromo(cp: Counterparty) {
    await api(`/api/v1/counterparties/${cp.id}/promo`, {
      method: "PATCH",
      body: JSON.stringify({ is_promo: !cp.is_promo }),
    });
    await loadCounterparties();
  }

  async function runDigest(send: boolean) {
    setDigestPreview("");
    try {
      const result = await api<{ sent: boolean; preview: string; reason?: string }>(
        "/api/v1/digest/run",
        {
          method: "POST",
          body: JSON.stringify({ year: digestYear, quarter: digestQuarter, send }),
        },
      );
      setDigestPreview(
        `${result.sent ? "Отправлено" : "Превью"}${result.reason ? ` (${result.reason})` : ""}\n\n${result.preview}`,
      );
    } catch (err) {
      setDigestPreview(err instanceof Error ? err.message : "Ошибка digest");
    }
  }

  return (
    <>
      <PageHeader
        title="Администрирование"
        subtitle="Подключения 1С, синхронизация, участники акции и digest"
        actions={
          <Link className="help-link" to="/help">
            Справка
          </Link>
        }
      />

      <div className="panel">
        <h2>Подключения 1С (OData)</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Рабочая база сейчас — <strong>asil</strong>. Вторую базу (miamor) подключим в конце: форма уже есть,
          но по умолчанию выключена.
        </p>
        {connMsg && <div className={`alert ${connMsg.includes("ok") || connMsg.includes("Сохранено") ? "ok" : ""}`}>{connMsg}</div>}
        {!connections.length && !connMsg && <p className="muted">Загрузка подключений…</p>}
        {connections.map((c) => (
          <div
            key={c.source_id}
            style={{
              border: "1px solid var(--line)",
              borderRadius: 12,
              padding: 16,
              marginBottom: 14,
              background: c.source_id === "miamor" ? "rgba(196,165,116,0.08)" : "#fff",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <div>
                <strong>{c.label || c.source_id}</strong>
                <span className="pill" style={{ marginLeft: 8 }}>
                  {c.source_id}
                </span>
                {c.source_id === "miamor" && <span className="pill gold" style={{ marginLeft: 8 }}>позже</span>}
              </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={c.enabled}
                  onChange={(e) => updateDraft(c.source_id, { enabled: e.target.checked })}
                />
                Включено
              </label>
            </div>
            <div className="grid-2">
              <label className="field" style={{ gridColumn: "1 / -1" }}>
                <span>Путь к базе (OData URL)</span>
                <input
                  value={c.base_url}
                  onChange={(e) => updateDraft(c.source_id, { base_url: e.target.value })}
                  placeholder="https://host/base/odata/standard.odata/"
                />
              </label>
              <label className="field">
                <span>Логин</span>
                <input
                  value={c.username}
                  onChange={(e) => updateDraft(c.source_id, { username: e.target.value })}
                  autoComplete="off"
                />
              </label>
              <label className="field">
                <span>Пароль {c.password_set ? "(сохранён, введите новый чтобы заменить)" : ""}</span>
                <input
                  type="password"
                  value={c.password}
                  onChange={(e) => updateDraft(c.source_id, { password: e.target.value })}
                  placeholder={c.password_set ? "••••••••" : ""}
                  autoComplete="new-password"
                />
              </label>
              <label className="toggle" style={{ alignSelf: "end", marginBottom: 8 }}>
                <input
                  type="checkbox"
                  checked={c.verify_ssl}
                  onChange={(e) => updateDraft(c.source_id, { verify_ssl: e.target.checked })}
                />
                Проверять SSL
              </label>
            </div>
            <div className="toolbar" style={{ marginTop: 12 }}>
              <button className="btn" onClick={() => saveConnection(c)}>
                Сохранить
              </button>
              <button className="btn secondary" onClick={() => testConnection(c.source_id)}>
                Проверить связь
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>Состояние</h2>
        {health && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span className={`pill ${health.status === "ok" ? "ok" : "warn"}`}>API {health.status}</span>
            <span className={`pill ${health.database === "ok" ? "ok" : "bad"}`}>DB {health.database}</span>
            <span className={`pill ${health.redis === "ok" ? "ok" : "warn"}`}>Redis {health.redis}</span>
            {Object.entries(health.odata || {}).map(([k, v]) => (
              <span key={k} className={`pill ${v === "ok" ? "ok" : "warn"}`}>
                {k}: {v}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Синхронизация OData</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          <strong>Инкремент</strong> — справочники, ЖЦТ, реализации, возвраты.{" "}
          <strong>Полный sync</strong> — плюс заказы клиентов и поступления из производства / товаров
          (нужны для факта отгрузок и вкладки «Производство», с 01.01.2025).
        </p>
        <div className="grid-3" style={{ marginBottom: 12 }}>
          <label className="field">
            <span>Источник</span>
            <Select
              value={sourceId}
              onChange={setSourceId}
              options={[
                { value: "asil", label: "asil" },
                { value: "", label: "Все включённые" },
                { value: "miamor", label: "miamor (когда включим)" },
              ]}
            />
          </label>
        </div>
        <div className="toolbar">
          <button className="btn" onClick={() => runSync(false)}>
            Инкремент
          </button>
          <button className="btn secondary" onClick={() => runSync(true)}>
            Полный sync
          </button>
          <button className="btn secondary" onClick={() => runSync(false, true)}>
            В очередь (Celery)
          </button>
        </div>
        {message && (
          <pre
            style={{
              whiteSpace: "pre-wrap",
              marginTop: 14,
              background: "#f8fafc",
              padding: 12,
              borderRadius: 10,
              border: "1px solid var(--line)",
              maxHeight: 240,
              overflow: "auto",
            }}
          >
            {message}
          </pre>
        )}
      </div>

      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey="admin-sync"
          rows={sync}
          rowKey={(s, idx) => `${s.source_id}-${s.entity}-${idx}`}
          columns={[
            { key: "source_id", title: "source", width: 100 },
            { key: "entity", title: "entity", width: 160 },
            { key: "status", title: "status", width: 110 },
            {
              key: "rows_synced",
              title: "rows",
              width: 90,
              align: "right",
            },
            {
              key: "last_incremental_at",
              title: "last incremental",
              width: 180,
              getValue: (s) => s.last_incremental_at || "",
              render: (s) => s.last_incremental_at || "—",
            },
            {
              key: "last_error",
              title: "error",
              width: 220,
              getValue: (s) => s.last_error || "",
              render: (s) => s.last_error || "",
            },
          ]}
        />
      </div>

      <div className="panel">
        <h2>Участники акции</h2>
        <div className="grid-3" style={{ marginBottom: 12 }}>
          <label className="field">
            <span>Поиск</span>
            <input value={cpQ} onChange={(e) => setCpQ(e.target.value)} placeholder="Имя" />
          </label>
          <label className="field">
            <span>База</span>
            <Select
              value={sourceId}
              onChange={setSourceId}
              options={[
                { value: "", label: "Все" },
                { value: "asil", label: "asil" },
                { value: "miamor", label: "miamor" },
              ]}
            />
          </label>
          <label className="toggle" style={{ alignSelf: "end", marginBottom: 8 }}>
            <input type="checkbox" checked={promoOnly} onChange={(e) => setPromoOnly(e.target.checked)} />
            Только promo
          </label>
        </div>
        <DataTable
          storageKey="admin-promo"
          rows={cps.slice(0, 100)}
          rowKey={(cp) => cp.id}
          columns={[
            { key: "name", title: "Контрагент", width: 240, sticky: true },
            { key: "source_id", title: "source", width: 100 },
            {
              key: "work_type",
              title: "Тип работы",
              width: 130,
              getValue: (cp) => cp.work_type || "",
              render: (cp) => cp.work_type || "—",
            },
            {
              key: "is_promo",
              title: "Акция",
              width: 120,
              sortable: false,
              getValue: (cp) => (cp.is_promo ? 1 : 0),
              render: (cp) => (
                <label className="toggle" onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={cp.is_promo} onChange={() => togglePromo(cp)} />
                  {cp.is_promo ? "да" : "нет"}
                </label>
              ),
            },
          ]}
        />
      </div>

      <div className="panel">
        <h2>Digest план/факт</h2>
        <div className="grid-3" style={{ marginBottom: 12 }}>
          <label className="field">
            <span>Год</span>
            <input
              type="number"
              value={digestYear}
              onChange={(e) => setDigestYear(Number(e.target.value))}
            />
          </label>
          <label className="field">
            <span>Квартал</span>
            <input
              type="number"
              min={1}
              max={4}
              value={digestQuarter}
              onChange={(e) => setDigestQuarter(Number(e.target.value))}
            />
          </label>
        </div>
        <div className="toolbar">
          <button className="btn secondary" onClick={() => runDigest(false)}>
            Превью
          </button>
          <button className="btn" onClick={() => runDigest(true)}>
            Отправить (SMTP)
          </button>
        </div>
        {digestPreview && (
          <pre
            style={{
              whiteSpace: "pre-wrap",
              marginTop: 14,
              background: "#f8fafc",
              padding: 12,
              borderRadius: 10,
              border: "1px solid var(--line)",
            }}
          >
            {digestPreview}
          </pre>
        )}
      </div>
    </>
  );
}
