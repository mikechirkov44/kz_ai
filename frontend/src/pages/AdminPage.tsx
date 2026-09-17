import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, Counterparty, listCounterparties } from "../api";
import Checkbox from "../components/Checkbox";
import DataTable from "../components/DataTable";
import DatePicker from "../components/DatePicker";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";
import SourceSelect from "../components/SourceSelect";
import SyncProgress from "../components/SyncProgress";
import { formatRuDateTime } from "../months";
import { sourceLabel } from "../odataSources";
import { allVisibleSelected, setVisibleSelection, syncActivityAt, syncIsBusy, syncRowKey } from "../syncProgress";
import { workTypeLabel } from "../workType";
import {
  applyScheduleFrequency,
  DEFAULT_RUN_AT,
  scheduleFrequencyValue,
  SYNC_AT_TIME,
  SYNC_FREQUENCY_OPTIONS,
  WEEKDAY_OPTIONS,
  syncScheduleEnvHint,
  toggleWeekday,
} from "../syncSchedule";

type Sync = {
  source_id: string;
  entity: string;
  status: string;
  rows_synced: number;
  rows_done?: number;
  rows_expected?: number;
  last_error?: string;
  last_incremental_at?: string;
  updated_at?: string;
  since_date?: string | null;
  date_filter?: boolean;
};

const SYNC_ENTITY_LABELS: Record<string, string> = {
  nomenclature: "Номенклатура",
  counterparty: "Контрагенты",
  realization: "Реализации",
  return_doc: "Возвраты",
  client_order: "Заказы",
  production_receipt: "Поступления 1С",
  lts_history: "ЖЦТ",
  object_properties: "Свойства объектов",
};

function syncEntityLabel(entity: string): string {
  return SYNC_ENTITY_LABELS[entity] || entity;
}

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
  base_url: "https://openrouter.ai/api/v1",
  model: "openrouter/free",
  api_key_set: false,
  timeout_seconds: 20,
  api_key: "",
};

type LlmModelGroup = {
  id: string;
  label: string;
  models: { id: string; name: string; price_label: string }[];
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

type SyncSchedule = {
  enabled: boolean;
  mode: "interval" | "at_time";
  interval_minutes: number;
  run_at: string;
  weekdays: number[];
  timezone: string;
  env_sync_enabled: boolean;
};

const emptySchedule: SyncSchedule = {
  enabled: true,
  mode: "interval",
  interval_minutes: 15,
  run_at: DEFAULT_RUN_AT,
  weekdays: [0, 1, 2, 3, 4, 5, 6],
  timezone: "Asia/Almaty",
  env_sync_enabled: false,
};

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
  const [message, setMessage] = useState("");
  const [sourceId, setSourceId] = useState("");
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
  const [llmModelSearch, setLlmModelSearch] = useState("");
  const [llmModelGroups, setLlmModelGroups] = useState<LlmModelGroup[]>([]);
  const [mail, setMail] = useState<MailDraft>(emptyMail);
  const [mailMsg, setMailMsg] = useState("");
  const [schedule, setSchedule] = useState<SyncSchedule>(emptySchedule);
  const [scheduleMsg, setScheduleMsg] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  async function refresh() {
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

  async function loadLlmModels() {
    try {
      const data = await api<{ groups?: LlmModelGroup[] }>("/api/v1/llm/models");
      setLlmModelGroups(data.groups || []);
    } catch {
      setLlmModelGroups([]);
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

  async function loadSchedule() {
    try {
      const row = await api<SyncSchedule>("/api/v1/sync/schedule");
      setSchedule(row);
      setScheduleMsg("");
    } catch (err) {
      setSchedule(emptySchedule);
      setScheduleMsg(err instanceof Error ? err.message : "Не удалось загрузить расписание");
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
    loadLlmModels().catch(() => setLlmModelGroups([]));
    loadMail().catch(() => setMail(emptyMail));
    loadSchedule().catch(() => setSchedule(emptySchedule));
  }, []);

  const syncBusy = useMemo(() => sync.some((row) => syncIsBusy(row.status)), [sync]);
  const llmModelOptions = useMemo(() => {
    const query = llmModelSearch.trim().toLowerCase();
    const options: { value: string; label: string }[] = [];
    for (const group of llmModelGroups) {
      for (const model of group.models) {
        const label = `${group.label} · ${model.name} · ${model.price_label}`;
        const hay = `${model.id} ${label}`.toLowerCase();
        if (query && !hay.includes(query)) continue;
        options.push({ value: model.id, label });
      }
    }
    if (llm.model && !options.some((item) => item.value === llm.model)) {
      options.unshift({ value: llm.model, label: llm.model });
    }
    return options;
  }, [llmModelGroups, llm.model, llmModelSearch]);
  useEffect(() => {
    if (tab !== "sync") return;
    const ms = syncBusy ? 1500 : 5000;
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, ms);
    return () => window.clearInterval(timer);
  }, [tab, syncBusy]);

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
      setConnMsg(`Сохранено: ${saved.label || c.label}`);
      await refresh();
    } catch (err) {
      setConnMsg(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function testConnection(c: ConnDraft) {
    setConnMsg("Проверка…");
    try {
      const res = await api<{ status: string }>(`/api/v1/odata/connections/${c.source_id}/test`, {
        method: "POST",
      });
      setConnMsg(`${c.label || "Подключение"}: ${res.status}`);
      await refresh();
    } catch (err) {
      setConnMsg(err instanceof Error ? err.message : "Ошибка проверки");
    }
  }

  async function addConnection() {
    setConnMsg("");
    try {
      const saved = await api<ODataConn>("/api/v1/odata/connections", {
        method: "POST",
        body: JSON.stringify({ label: "Новая база", enabled: false }),
      });
      setConnections((prev) => [...prev, { ...saved, password: "" }]);
      setConnMsg(`Добавлено: ${saved.label}`);
    } catch (err) {
      setConnMsg(err instanceof Error ? err.message : "Не удалось добавить подключение");
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

  async function saveSchedule() {
    setScheduleMsg("");
    try {
      const saved = await api<SyncSchedule>("/api/v1/sync/schedule", {
        method: "PUT",
        body: JSON.stringify({
          enabled: schedule.enabled,
          mode: schedule.mode,
          interval_minutes: schedule.interval_minutes,
          run_at: schedule.run_at,
          weekdays: schedule.weekdays,
        }),
      });
      setSchedule(saved);
      setScheduleMsg("Сохранено");
    } catch (err) {
      setScheduleMsg(err instanceof Error ? err.message : "Ошибка сохранения");
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

  async function runSync(full: boolean, items?: { source_id: string; entity: string }[]) {
    setMessage("Ставим в очередь…");
    try {
      const params = new URLSearchParams({
        full: String(full),
        background: "true",
      });
      if (!items?.length && sourceId) params.set("source_id", sourceId);
      const result = await api<Record<string, unknown>>(`/api/v1/sync/run?${params}`, {
        method: "POST",
        body: JSON.stringify({ items: items || [] }),
      });
      if (result.queued) {
        const count = typeof result.count === "number" ? result.count : items?.length || 0;
        setMessage(count ? `В очереди объектов: ${count}` : "Задача поставлена в очередь");
      } else {
        setMessage("Синхронизация завершена");
      }
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка синка");
    }
  }

  function toggleSelected(row: Sync) {
    const key = syncRowKey(row.source_id, row.entity);
    setSelected((prev) => (prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]));
  }

  function selectedItems(): { source_id: string; entity: string }[] {
    const allowed = new Set(sync.map((row) => syncRowKey(row.source_id, row.entity)));
    return selected
      .filter((key) => allowed.has(key))
      .map((key) => {
        const [source_id, entity] = key.split(":");
        return { source_id, entity };
      });
  }

  async function saveSince(row: Sync, value: string) {
    try {
      const updated = await api<Sync>("/api/v1/sync/since", {
        method: "PATCH",
        body: JSON.stringify({
          source_id: row.source_id,
          entity: row.entity,
          since_date: value || null,
        }),
      });
      setSync((prev) =>
        prev.map((s) =>
          s.source_id === row.source_id && s.entity === row.entity ? { ...s, ...updated } : s,
        ),
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Не удалось сохранить дату");
      await refresh();
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

  const sourceOptions = connections.map((c) => ({
    source_id: c.source_id,
    label: c.label || c.source_id,
    enabled: c.enabled,
  }));
  const visibleSyncKeys = useMemo(
    () => sync.map((row) => syncRowKey(row.source_id, row.entity)),
    [sync],
  );
  const allSyncSelected = allVisibleSelected(selected, visibleSyncKeys);

  return (
    <>
      <PageHeader
        title="Администрирование"
        subtitle="1С, синхронизация, LLM и рассылка"
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
        {tab === "odata" && (
        <AdminBlock
          title="Подключения 1С"
          hint="Имя любое — так база будет называться в фильтрах. URL и логин — из публикации OData."
        >
          <div className="panel">
            {connMsg && (
              <div
                className={`alert ${
                  connMsg.includes("ok") || connMsg.includes("Сохранено") || connMsg.includes("Добавлено")
                    ? "ok"
                    : ""
                }`}
              >
                {connMsg}
              </div>
            )}
            {!connections.length && !connMsg && <p className="muted">Загрузка подключений…</p>}
            {connections.map((c) => (
              <div key={c.source_id} className="admin-card">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                    marginBottom: 12,
                    alignItems: "end",
                  }}
                >
                  <label className="field" style={{ flex: "1 1 240px", marginBottom: 0 }}>
                    <span>Имя</span>
                    <input
                      value={c.label}
                      onChange={(e) => updateDraft(c.source_id, { label: e.target.value })}
                      placeholder="Как называть базу в отчётах"
                    />
                  </label>
                  <Checkbox
                    className="toggle"
                    style={{ marginBottom: 8 }}
                    checked={c.enabled}
                    onChange={(enabled) => updateDraft(c.source_id, { enabled })}
                  >
                    Включено
                  </Checkbox>
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
                  <Checkbox
                    className="toggle"
                    style={{ alignSelf: "end", marginBottom: 8 }}
                    checked={c.verify_ssl}
                    onChange={(verify_ssl) => updateDraft(c.source_id, { verify_ssl })}
                  >
                    Проверять SSL
                  </Checkbox>
                </div>
                <div className="toolbar" style={{ marginTop: 12 }}>
                  <button className="btn" onClick={() => saveConnection(c)}>
                    Сохранить
                  </button>
                  <button className="btn secondary" onClick={() => testConnection(c)}>
                    Проверить связь
                  </button>
                </div>
              </div>
            ))}
            <div className="toolbar" style={{ marginTop: 8 }}>
              <button className="btn secondary" onClick={addConnection}>
                Добавить подключение
              </button>
            </div>
          </div>
        </AdminBlock>
        )}

        {tab === "sync" && (
        <AdminBlock
          title="Синхронизация"
          hint="Дата «С даты» ограничивает загрузку документов (пустая — без ограничения). Уже загруженные строки не удаляются. Полная синхронизация — только вручную."
        >
          <div className="panel">
            <h3 style={{ margin: "0 0 8px", fontSize: "1rem" }}>Автообновление</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              {syncScheduleEnvHint(schedule.timezone)}
            </p>
            {scheduleMsg && (
              <div className={`alert ${scheduleMsg === "Сохранено" ? "ok" : ""}`}>{scheduleMsg}</div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
              <Checkbox
                className="toggle"
                checked={schedule.enabled}
                onChange={(enabled) => setSchedule((prev) => ({ ...prev, enabled }))}
              >
                Включено
              </Checkbox>
            </div>
            <div className="grid-2" style={{ marginBottom: 12 }}>
              <label className="field">
                <span>Периодичность</span>
                <Select
                  value={scheduleFrequencyValue(schedule)}
                  options={SYNC_FREQUENCY_OPTIONS}
                  onChange={(value) => setSchedule((prev) => applyScheduleFrequency(prev, value))}
                />
              </label>
              {schedule.mode === SYNC_AT_TIME && (
                <label className="field">
                  <span>Время</span>
                  <input
                    type="time"
                    value={schedule.run_at || DEFAULT_RUN_AT}
                    onChange={(e) => setSchedule((prev) => ({ ...prev, run_at: e.target.value || DEFAULT_RUN_AT }))}
                  />
                </label>
              )}
              <div className="field" style={{ gridColumn: "1 / -1" }}>
                <span>Дни недели</span>
                <div className="seg-tabs" style={{ marginBottom: 0 }} role="group" aria-label="Дни недели">
                  {WEEKDAY_OPTIONS.map((day) => (
                    <button
                      key={day.value}
                      type="button"
                      className={`seg-tab ${schedule.weekdays.includes(day.value) ? "active" : ""}`}
                      onClick={() =>
                        setSchedule((prev) => ({ ...prev, weekdays: toggleWeekday(prev.weekdays, day.value) }))
                      }
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="toolbar" style={{ marginBottom: 16 }}>
              <button className="btn" onClick={() => void saveSchedule()}>
                Сохранить расписание
              </button>
            </div>
            <div className="grid-3" style={{ marginBottom: 12 }}>
              <label className="field">
                <span>Источник</span>
                <SourceSelect
                  value={sourceId}
                  onChange={setSourceId}
                  sources={sourceOptions}
                  emptyLabel="Все включённые"
                />
              </label>
            </div>
            <div className="toolbar">
              <button className="btn" onClick={() => void runSync(false)}>
                Обновить данные
              </button>
              <button className="btn secondary" onClick={() => void runSync(true)}>
                Полная синхронизация
              </button>
              <button
                className="btn secondary"
                disabled={!selectedItems().length}
                onClick={() => {
                  const items = selectedItems();
                  if (!items.length) return;
                  void runSync(false, items);
                }}
              >
                Запустить выбранные
              </button>
            </div>
            {message && <p className="sync-run-msg">{message}</p>}
          </div>
          <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <DataTable
              storageKey="admin-sync"
              rows={sync}
              rowKey={(s) => syncRowKey(s.source_id, s.entity)}
              rowClassName={(s) => `sync-row is-${s.status}`}
              columns={[
                {
                  key: "pick",
                  title: (
                    <Checkbox
                      checked={allSyncSelected}
                      disabled={!visibleSyncKeys.length}
                      onChange={(on) => setSelected((prev) => setVisibleSelection(prev, visibleSyncKeys, on))}
                      onClick={(e) => e.stopPropagation()}
                      aria-label="Выбрать все"
                    />
                  ),
                  width: 44,
                  sortable: false,
                  align: "center",
                  render: (s) => (
                    <Checkbox
                      checked={selected.includes(syncRowKey(s.source_id, s.entity))}
                      onChange={() => toggleSelected(s)}
                      onClick={(e) => e.stopPropagation()}
                      aria-label={`Выбрать ${syncEntityLabel(s.entity)}`}
                    />
                  ),
                },
                {
                  key: "source_id",
                  title: "База",
                  width: 140,
                  getValue: (s) => sourceLabel(s.source_id, sourceOptions),
                  render: (s) => sourceLabel(s.source_id, sourceOptions),
                },
                {
                  key: "entity",
                  title: "Объект",
                  width: 160,
                  getValue: (s) => syncEntityLabel(s.entity),
                  render: (s) => syncEntityLabel(s.entity),
                },
                {
                  key: "since_date",
                  title: "С даты",
                  width: 180,
                  sortable: false,
                  getValue: (s) => s.since_date || "",
                  render: (s) =>
                    s.date_filter ? (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        onMouseDown={(e) => e.stopPropagation()}
                      >
                        <DatePicker
                          value={s.since_date || ""}
                          allowClear
                          placeholder="без ограничения"
                          onChange={(value) => {
                            void saveSince(s, value);
                          }}
                        />
                      </div>
                    ) : (
                      <span className="sync-since-muted">весь справочник</span>
                    ),
                },
                {
                  key: "status",
                  title: "Статус",
                  width: 220,
                  getValue: (s) => s.status,
                  render: (s) => (
                    <SyncProgress
                      status={s.status}
                      entity={s.entity}
                      rowsDone={s.rows_done ?? 0}
                      rowsExpected={s.rows_expected ?? 0}
                      rowsSynced={s.rows_synced}
                    />
                  ),
                },
                {
                  key: "run",
                  title: "",
                  width: 52,
                  sortable: false,
                  render: (s) => (
                    <button
                      type="button"
                      className="sync-run-one"
                      title="Запустить этот объект"
                      aria-label={`Запустить ${syncEntityLabel(s.entity)}`}
                      disabled={syncIsBusy(s.status)}
                      onClick={(e) => {
                        e.stopPropagation();
                        void runSync(false, [{ source_id: s.source_id, entity: s.entity }]);
                      }}
                    >
                      ▶
                    </button>
                  ),
                },
                {
                  key: "last_incremental_at",
                  title: "Последнее обновление",
                  width: 200,
                  getValue: (s) =>
                    syncActivityAt({
                      status: s.status,
                      lastIncrementalAt: s.last_incremental_at,
                      updatedAt: s.updated_at,
                    }),
                  render: (s) =>
                    formatRuDateTime(
                      syncActivityAt({
                        status: s.status,
                        lastIncrementalAt: s.last_incremental_at,
                        updatedAt: s.updated_at,
                      }),
                    ) || "—",
                },
                {
                  key: "last_error",
                  title: "Ошибка",
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
              <Checkbox
                className="toggle"
                checked={llm.enabled}
                onChange={(enabled) => setLlm((prev) => ({ ...prev, enabled }))}
              >
                Включено
              </Checkbox>
            </div>
            <div className="grid-2">
              <label className="field" style={{ gridColumn: "1 / -1" }}>
                <span>Адрес API</span>
                <input
                  value={llm.base_url}
                  onChange={(e) => setLlm((prev) => ({ ...prev, base_url: e.target.value }))}
                  placeholder="https://openrouter.ai/api/v1"
                />
              </label>
              <label className="field" style={{ gridColumn: "1 / -1" }}>
                <span>Модель</span>
                <Select
                  value={llm.model}
                  onChange={(value) => setLlm((prev) => ({ ...prev, model: value }))}
                  options={llmModelOptions}
                  placeholder="Free, недорого или премиум"
                  search={llmModelSearch}
                  onSearch={setLlmModelSearch}
                  searchPlaceholder="Поиск по названию или id"
                  allowCreate
                />
                <span className="muted" style={{ marginTop: 6, display: "block" }}>
                  Бесплатные модели OpenRouter — только с суффиксом :free (или openrouter/free). gpt-4o-mini платная.
                  Кредитная линия в кабинете не заменяет пополнение Credits: без купленных кредитов Free тоже ответит 402.
                </span>
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
        <AdminBlock title="Участники акции" hint="Нужен для мотивации и оборачиваемости по акции.">
          <div className="panel">
            <div className="grid-3" style={{ marginBottom: 12 }}>
              <label className="field">
                <span>Поиск</span>
                <input value={cpQ} onChange={(e) => setCpQ(e.target.value)} placeholder="Имя" />
              </label>
              <label className="field">
                <span>База</span>
                <SourceSelect value={sourceId} onChange={setSourceId} sources={sourceOptions} />
              </label>
              <Checkbox
                className="toggle"
                style={{ alignSelf: "end", marginBottom: 8 }}
                checked={promoOnly}
                onChange={setPromoOnly}
              >
                Только акция
              </Checkbox>
            </div>
            <DataTable
              storageKey="admin-promo"
              rows={cps.slice(0, 100)}
              rowKey={(cp) => cp.id}
              columns={[
                { key: "name", title: "Контрагент", width: 240, sticky: true },
                {
                  key: "source_id",
                  title: "База",
                  width: 140,
                  getValue: (cp) => sourceLabel(cp.source_id, sourceOptions),
                  render: (cp) => sourceLabel(cp.source_id, sourceOptions),
                },
                {
                  key: "work_type",
                  title: "Тип работы",
                  width: 130,
                  getValue: (cp) => workTypeLabel(cp.work_type_label || cp.work_type),
                  render: (cp) => workTypeLabel(cp.work_type_label || cp.work_type),
                },
                {
                  key: "is_promo",
                  title: "Акция",
                  width: 120,
                  sortable: false,
                  getValue: (cp) => (cp.is_promo ? 1 : 0),
                  render: (cp) => (
                    <Checkbox
                      className="toggle"
                      checked={cp.is_promo}
                      onChange={() => togglePromo(cp)}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {cp.is_promo ? "да" : "нет"}
                    </Checkbox>
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
        <AdminBlock title="Рассылка" hint="Письмо HTML и Excel по понедельникам в 08:00 по Алматы. Пароль почты на экран не показывается.">
          <div className="panel">
            <h3>Что рассылаем</h3>
            <div className="grid-3">
              <Checkbox
                className="toggle"
                checked={mail.include_quarterly}
                onChange={(include_quarterly) => setMail((prev) => ({ ...prev, include_quarterly }))}
              >
                Промежуточные и итоги квартала
              </Checkbox>
              <Checkbox
                className="toggle"
                checked={mail.include_behind}
                onChange={(include_behind) => setMail((prev) => ({ ...prev, include_behind }))}
              >
                Отстающие (&lt; 100%)
              </Checkbox>
              <Checkbox
                className="toggle"
                checked={mail.include_recommendations}
                onChange={(include_recommendations) => setMail((prev) => ({ ...prev, include_recommendations }))}
              >
                Рекомендации
              </Checkbox>
            </div>
          </div>
          <div className="panel">
            <h3>Почта</h3>
            {mailMsg && (
              <div className={`alert ${mailMsg.startsWith("ok") || mailMsg === "Сохранено" ? "ok" : ""}`}>{mailMsg}</div>
            )}
            <Checkbox
              className="toggle"
              style={{ marginBottom: 12 }}
              checked={mail.enabled}
              onChange={(enabled) => setMail((prev) => ({ ...prev, enabled }))}
            >
              Авторассылка включена
            </Checkbox>
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
              <Checkbox
                className="toggle"
                style={{ alignSelf: "end", marginBottom: 8 }}
                checked={mail.use_tls}
                onChange={(use_tls) => setMail((prev) => ({ ...prev, use_tls }))}
              >
                TLS (STARTTLS)
              </Checkbox>
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
