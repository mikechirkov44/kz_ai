import { useEffect, useState, type ReactNode } from "react";
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

type LlmSettings = {
  enabled: boolean;
  provider: string;
  base_url: string;
  model: string;
  api_key_set: boolean;
  timeout_seconds: number;
};

type LlmDraft = LlmSettings & { api_key: string };

const emptyLlm: LlmDraft = {
  enabled: false,
  provider: "openai_compatible",
  base_url: "https://api.openai.com/v1",
  model: "gpt-4o-mini",
  api_key_set: false,
  timeout_seconds: 20,
  api_key: "",
};

type MailSettings = {
  enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  password_set: boolean;
  smtp_from: string;
  use_tls: boolean;
  recipients: string;
  include_quarterly: boolean;
  include_behind: boolean;
  include_recommendations: boolean;
};

type MailDraft = MailSettings & { smtp_password: string };

const emptyMail: MailDraft = {
  enabled: false,
  smtp_host: "",
  smtp_port: 587,
  smtp_user: "",
  password_set: false,
  smtp_from: "",
  use_tls: true,
  recipients: "",
  include_quarterly: true,
  include_behind: true,
  include_recommendations: false,
  smtp_password: "",
};

const ADMIN_TABS = [
  { id: "health", label: "Состояние" },
  { id: "odata", label: "1С" },
  { id: "sync", label: "Синхронизация" },
  { id: "llm", label: "LLM" },
  { id: "promo", label: "Акция" },
  { id: "mail", label: "Рассылка" },
] as const;

type AdminTab = (typeof ADMIN_TABS)[number]["id"];

function AdminBlock({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="admin-block">
      <header className="admin-block-head">
        <h2>{title}</h2>
        {hint && <p className="muted">{hint}</p>}
      </header>
      <div className="admin-block-body">{children}</div>
    </section>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState<AdminTab>("odata");
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
  const [llm, setLlm] = useState<LlmDraft>(emptyLlm);
  const [llmMsg, setLlmMsg] = useState("");
  const [mail, setMail] = useState<MailDraft>(emptyMail);
  const [mailMsg, setMailMsg] = useState("");

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

  async function loadLlm() {
    try {
      const row = await api<LlmSettings>("/api/v1/llm/settings");
      setLlm({ ...row, api_key: "" });
      setLlmMsg("");
    } catch (err) {
      setLlm(emptyLlm);
      setLlmMsg(err instanceof Error ? err.message : "Не удалось загрузить настройки LLM");
    }
  }

  async function loadMail() {
    try {
      const row = await api<MailSettings>("/api/v1/mail/settings");
      setMail({ ...row, smtp_password: "" });
      setMailMsg("");
    } catch (err) {
      setMail(emptyMail);
      setMailMsg(err instanceof Error ? err.message : "Не удалось загрузить настройки рассылки");
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
    loadLlm().catch(() => setLlm(emptyLlm));
    loadMail().catch(() => setMail(emptyMail));
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

  async function saveLlm() {
    setLlmMsg("");
    try {
      const body: Record<string, unknown> = {
        enabled: llm.enabled,
        base_url: llm.base_url,
        model: llm.model,
        timeout_seconds: llm.timeout_seconds,
      };
      if (llm.api_key) body.api_key = llm.api_key;
      const saved = await api<LlmSettings>("/api/v1/llm/settings", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setLlm({ ...saved, api_key: "" });
      setLlmMsg("Сохранено");
    } catch (err) {
      setLlmMsg(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function testLlm() {
    setLlmMsg("Проверка…");
    try {
      const body: Record<string, unknown> = {
        base_url: llm.base_url,
        model: llm.model,
        timeout_seconds: llm.timeout_seconds,
      };
      if (llm.api_key) body.api_key = llm.api_key;
      const res = await api<{ status: string; detail?: string }>("/api/v1/llm/settings/test", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setLlmMsg(res.status === "ok" ? `ok${res.detail ? `: ${res.detail}` : ""}` : res.detail || "Ошибка проверки");
    } catch (err) {
      setLlmMsg(err instanceof Error ? err.message : "Ошибка проверки");
    }
  }

  async function saveMail() {
    setMailMsg("");
    try {
      const body: Record<string, unknown> = {
        enabled: mail.enabled,
        smtp_host: mail.smtp_host,
        smtp_port: mail.smtp_port,
        smtp_user: mail.smtp_user,
        smtp_from: mail.smtp_from,
        use_tls: mail.use_tls,
        recipients: mail.recipients,
        include_quarterly: mail.include_quarterly,
        include_behind: mail.include_behind,
        include_recommendations: mail.include_recommendations,
      };
      if (mail.smtp_password) body.smtp_password = mail.smtp_password;
      const saved = await api<MailSettings>("/api/v1/mail/settings", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setMail({ ...saved, smtp_password: "" });
      setMailMsg("Сохранено");
    } catch (err) {
      setMailMsg(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function testMail() {
    setMailMsg("Проверка…");
    try {
      const res = await api<{ status: string; detail?: string }>("/api/v1/mail/settings/test", {
        method: "POST",
      });
      setMailMsg(res.status === "ok" ? `ok${res.detail ? `: ${res.detail}` : ""}` : res.detail || "Ошибка проверки");
    } catch (err) {
      setMailMsg(err instanceof Error ? err.message : "Ошибка проверки");
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
        subtitle="Состояние, 1С, синхронизация, LLM, акция и рассылка. Пользователи и аудит — отдельные экраны."
        actions={
          <Link className="help-link" to="/help">
            Справка
          </Link>
        }
      />

      <div className="seg-tabs" role="tablist" aria-label="Разделы админки">
        {ADMIN_TABS.map((item) => (
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

      <div className="admin-blocks">
        {tab === "health" && (
        <AdminBlock title="Состояние системы" hint="API, база, Redis и проверка OData.">
          <div className="panel">
            {health ? (
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
            ) : (
              <p className="muted" style={{ margin: 0 }}>
                Загрузка…
              </p>
            )}
          </div>
        </AdminBlock>
        )}

        {tab === "odata" && (
        <AdminBlock
          title="Подключения 1С"
          hint="Рабочая база — asil. miamor подключим позже: форма есть, по умолчанию выключена."
        >
          <div className="panel">
            {connMsg && (
              <div className={`alert ${connMsg.includes("ok") || connMsg.includes("Сохранено") ? "ok" : ""}`}>
                {connMsg}
              </div>
            )}
            {!connections.length && !connMsg && <p className="muted">Загрузка подключений…</p>}
            {connections.map((c) => (
              <div
                key={c.source_id}
                className="admin-card"
                style={{ background: c.source_id === "miamor" ? "rgba(196,165,116,0.08)" : "#fff" }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
                  <div>
                    <strong>{c.label || c.source_id}</strong>
                    <span className="pill" style={{ marginLeft: 8 }}>
                      {c.source_id}
                    </span>
                    {c.source_id === "miamor" && (
                      <span className="pill gold" style={{ marginLeft: 8 }}>
                        позже
                      </span>
                    )}
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
        </AdminBlock>
        )}

        {tab === "sync" && (
        <AdminBlock
          title="Синхронизация"
          hint="Инкремент — справочники, ЖЦТ, реализации, возвраты. Полный sync — плюс заказы и поступления из производства (с 01.01.2025)."
        >
          <div className="panel">
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
                Инкремент в очередь
              </button>
              <button className="btn secondary" onClick={() => runSync(true, true)}>
                Полный sync в очередь
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
        </AdminBlock>
        )}

        {tab === "llm" && (
        <AdminBlock
          title="LLM для рекомендаций"
          hint="OpenAI-совместимый API. Правила остаются основой: модель добавляет короткий совет менеджеру. При сбое API показываются только правила."
        >
          <div className="panel">
            {llmMsg && (
              <div className={`alert ${llmMsg.startsWith("ok") || llmMsg === "Сохранено" ? "ok" : ""}`}>{llmMsg}</div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={llm.enabled}
                  onChange={(e) => setLlm((prev) => ({ ...prev, enabled: e.target.checked }))}
                />
                Включено
              </label>
            </div>
            <div className="grid-2">
              <label className="field" style={{ gridColumn: "1 / -1" }}>
                <span>Адрес API</span>
                <input
                  value={llm.base_url}
                  onChange={(e) => setLlm((prev) => ({ ...prev, base_url: e.target.value }))}
                  placeholder="https://api.openai.com/v1"
                />
              </label>
              <label className="field">
                <span>Модель</span>
                <input
                  value={llm.model}
                  onChange={(e) => setLlm((prev) => ({ ...prev, model: e.target.value }))}
                  placeholder="gpt-4o-mini"
                />
              </label>
              <label className="field">
                <span>Ключ API {llm.api_key_set ? "(сохранён, введите новый чтобы заменить)" : ""}</span>
                <input
                  type="password"
                  value={llm.api_key}
                  onChange={(e) => setLlm((prev) => ({ ...prev, api_key: e.target.value }))}
                  placeholder={llm.api_key_set ? "••••••••" : ""}
                  autoComplete="new-password"
                />
              </label>
              <label className="field">
                <span>Таймаут, сек</span>
                <input
                  type="number"
                  min={5}
                  max={120}
                  value={llm.timeout_seconds}
                  onChange={(e) => setLlm((prev) => ({ ...prev, timeout_seconds: Number(e.target.value) || 20 }))}
                />
              </label>
            </div>
            <div className="toolbar" style={{ marginTop: 12 }}>
              <button className="btn" onClick={saveLlm}>
                Сохранить
              </button>
              <button className="btn secondary" onClick={testLlm}>
                Проверить связь
              </button>
            </div>
          </div>
        </AdminBlock>
        )}

        {tab === "promo" && (
        <AdminBlock title="Участники акции" hint="Флаг is_promo нужен для мотивации и оборачиваемости по акции.">
          <div className="panel">
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
                {
                  key: "manager_name",
                  title: "Менеджер",
                  width: 160,
                  getValue: (cp) => cp.manager_name || "",
                  render: (cp) => cp.manager_name || "—",
                },
              ]}
            />
          </div>
        </AdminBlock>
        )}

        {tab === "mail" && (
        <AdminBlock title="Рассылка" hint="Письмо план/факт по понедельникам в 08:00 (Asia/Almaty). Пароль SMTP шифруется, на экран не отдаётся.">
          <div className="panel">
            <h3>Что рассылаем</h3>
            <div className="grid-3">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={mail.include_quarterly}
                  onChange={(e) => setMail((prev) => ({ ...prev, include_quarterly: e.target.checked }))}
                />
                План/факт по клиентам
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={mail.include_behind}
                  onChange={(e) => setMail((prev) => ({ ...prev, include_behind: e.target.checked }))}
                />
                Отстающие (&lt; 100%)
              </label>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={mail.include_recommendations}
                  onChange={(e) => setMail((prev) => ({ ...prev, include_recommendations: e.target.checked }))}
                />
                Рекомендации
              </label>
            </div>
          </div>
          <div className="panel">
            <h3>Почта</h3>
            {mailMsg && (
              <div className={`alert ${mailMsg.startsWith("ok") || mailMsg === "Сохранено" ? "ok" : ""}`}>{mailMsg}</div>
            )}
            <label className="toggle" style={{ marginBottom: 12 }}>
              <input
                type="checkbox"
                checked={mail.enabled}
                onChange={(e) => setMail((prev) => ({ ...prev, enabled: e.target.checked }))}
              />
              Авторассылка включена
            </label>
            <div className="grid-2">
              <label className="field">
                <span>SMTP-сервер</span>
                <input
                  value={mail.smtp_host}
                  onChange={(e) => setMail((prev) => ({ ...prev, smtp_host: e.target.value }))}
                  placeholder="smtp.example.com"
                />
              </label>
              <label className="field">
                <span>Порт</span>
                <input
                  type="number"
                  min={1}
                  max={65535}
                  value={mail.smtp_port}
                  onChange={(e) => setMail((prev) => ({ ...prev, smtp_port: Number(e.target.value) || 587 }))}
                />
              </label>
              <label className="field">
                <span>Логин SMTP</span>
                <input
                  value={mail.smtp_user}
                  onChange={(e) => setMail((prev) => ({ ...prev, smtp_user: e.target.value }))}
                  autoComplete="off"
                />
              </label>
              <label className="field">
                <span>Пароль {mail.password_set ? "(сохранён, введите новый чтобы заменить)" : ""}</span>
                <input
                  type="password"
                  value={mail.smtp_password}
                  onChange={(e) => setMail((prev) => ({ ...prev, smtp_password: e.target.value }))}
                  placeholder={mail.password_set ? "••••••••" : ""}
                  autoComplete="new-password"
                />
              </label>
              <label className="field">
                <span>От кого</span>
                <input
                  value={mail.smtp_from}
                  onChange={(e) => setMail((prev) => ({ ...prev, smtp_from: e.target.value }))}
                  placeholder="noreply@example.com"
                />
              </label>
              <label className="toggle" style={{ alignSelf: "end", marginBottom: 8 }}>
                <input
                  type="checkbox"
                  checked={mail.use_tls}
                  onChange={(e) => setMail((prev) => ({ ...prev, use_tls: e.target.checked }))}
                />
                TLS (STARTTLS)
              </label>
              <label className="field" style={{ gridColumn: "1 / -1" }}>
                <span>Кому (через запятую)</span>
                <input
                  value={mail.recipients}
                  onChange={(e) => setMail((prev) => ({ ...prev, recipients: e.target.value }))}
                  placeholder="name@example.com"
                />
              </label>
            </div>
            <div className="toolbar" style={{ marginTop: 12 }}>
              <button className="btn" type="button" onClick={saveMail}>
                Сохранить
              </button>
              <button className="btn secondary" type="button" onClick={testMail}>
                Проверить SMTP
              </button>
            </div>
          </div>
          <div className="panel">
            <h3>Превью и отправка сейчас</h3>
            <div className="grid-3" style={{ marginBottom: 12 }}>
              <label className="field">
                <span>Год</span>
                <input type="number" value={digestYear} onChange={(e) => setDigestYear(Number(e.target.value))} />
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
              <button className="btn secondary" type="button" onClick={() => runDigest(false)}>
                Превью
              </button>
              <button className="btn" type="button" onClick={() => runDigest(true)}>
                Отправить сейчас
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
                  maxHeight: 280,
                  overflow: "auto",
                }}
              >
                {digestPreview}
              </pre>
            )}
          </div>
        </AdminBlock>
        )}
      </div>
    </>
  );
}
