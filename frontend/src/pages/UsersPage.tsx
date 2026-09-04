import { FormEvent, useEffect, useState } from "react";
import { api, ROLE_LABELS, type Me } from "../api";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";

const ROLE_OPTIONS = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }));

export default function UsersPage() {
  const [users, setUsers] = useState<Me[]>([]);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Me | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("manager");
  const [fullName, setFullName] = useState("");
  const [region, setRegion] = useState("");
  const [active, setActive] = useState(true);

  async function load() {
    setError("");
    try {
      setUsers(await api<Me[]>("/api/v1/auth/users"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить пользователей");
    }
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  function startCreate() {
    setEditing(null);
    setEmail("");
    setPassword("");
    setRole("manager");
    setFullName("");
    setRegion("");
    setActive(true);
    setOpen(true);
  }

  function startEdit(u: Me) {
    setEditing(u);
    setEmail(u.email);
    setPassword("");
    setRole(u.role);
    setFullName(u.full_name || "");
    setRegion(u.region || "");
    setActive(u.active);
    setOpen(true);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      if (editing) {
        const body: Record<string, unknown> = {
          role,
          full_name: fullName || null,
          region: region || null,
          active,
        };
        if (password) body.password = password;
        await api(`/api/v1/auth/users/${editing.id}`, { method: "PATCH", body: JSON.stringify(body) });
      } else {
        await api("/api/v1/auth/users", {
          method: "POST",
          body: JSON.stringify({
            email,
            password,
            role,
            full_name: fullName || null,
            region: region || null,
          }),
        });
      }
      setOpen(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  return (
    <>
      <PageHeader
        title="Пользователи"
        subtitle="Создание, роли и деактивация. Менеджеров затем закрепляют за контрагентами."
        actions={
          <button className="btn" type="button" onClick={startCreate}>
            Новый пользователь
          </button>
        }
      />
      {error && <div className="alert">{error}</div>}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey="users"
          rows={users}
          rowKey={(u) => u.id}
          onRowClick={startEdit}
          columns={[
            { key: "email", title: "Email", width: 220, sticky: true },
            {
              key: "full_name",
              title: "ФИО",
              width: 180,
              getValue: (u) => u.full_name || "",
              render: (u) => u.full_name || "—",
            },
            {
              key: "role",
              title: "Роль",
              width: 150,
              getValue: (u) => u.role,
              render: (u) => ROLE_LABELS[u.role] || u.role,
            },
            {
              key: "region",
              title: "Регион",
              width: 120,
              getValue: (u) => u.region || "",
              render: (u) => u.region || "—",
            },
            {
              key: "active",
              title: "Активен",
              width: 100,
              getValue: (u) => (u.active ? 1 : 0),
              render: (u) => (u.active ? "да" : "нет"),
            },
          ]}
        />
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Изменить пользователя" : "Новый пользователь"}
      >
        <form onSubmit={onSubmit}>
          <div className="grid-2">
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required={!editing}
                disabled={!!editing}
              />
            </label>
            <label className="field">
              <span>{editing ? "Новый пароль (пусто = не менять)" : "Пароль"}</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={editing ? undefined : 8}
                required={!editing}
              />
            </label>
            <label className="field">
              <span>Роль</span>
              <Select value={role} onChange={setRole} options={ROLE_OPTIONS} />
            </label>
            <label className="field">
              <span>ФИО</span>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </label>
            <label className="field">
              <span>Регион</span>
              <input value={region} onChange={(e) => setRegion(e.target.value)} />
            </label>
            {editing && (
              <label className="toggle" style={{ alignSelf: "end", marginBottom: 8 }}>
                <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                Активен
              </label>
            )}
          </div>
          <div className="toolbar" style={{ marginTop: 16 }}>
            <button className="btn" type="submit">
              Сохранить
            </button>
            <button className="btn secondary" type="button" onClick={() => setOpen(false)}>
              Отмена
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
