import { FormEvent, useEffect, useState } from "react";
import { api, downloadFile, formatMoney } from "../api";
import PageHeader from "../components/PageHeader";
import Pager from "../components/Pager";
import RowActionsMenu from "../components/RowActionsMenu";

export type RegisterKind = "sales" | "stocks" | "promo";

export type RegisterRow = {
  id: string;
  counterparty_name: string;
  article: string;
  shop?: string | null;
  quantity: number;
  price?: number | null;
  period_year?: number | null;
  period_month?: number | null;
  stock_date?: string | null;
};

const KINDS: { id: RegisterKind; label: string }[] = [
  { id: "sales", label: "Продажи" },
  { id: "stocks", label: "Остатки" },
  { id: "promo", label: "Доп. мотивация" },
];

const EMPTY_SHOP = new Set(["nan", "none", "null", "nat"]);

type Draft = { article: string; shop: string; quantity: string };

export function registerShopLabel(shop?: string | null): string {
  const text = (shop ?? "").trim();
  if (!text || EMPTY_SHOP.has(text.toLowerCase())) return "";
  return text;
}

function draftOf(row: RegisterRow): Draft {
  return { article: row.article, shop: registerShopLabel(row.shop), quantity: String(row.quantity) };
}

function periodLabel(row: RegisterRow): string {
  if (row.period_year && row.period_month) {
    return `${row.period_year}-${String(row.period_month).padStart(2, "0")}`;
  }
  return "—";
}

export function RegisterTable({
  kind,
  rows,
  editingId,
  draft,
  busyId,
  onDraft,
  onEdit,
  onCancel,
  onSave,
  onDelete,
}: {
  kind: RegisterKind;
  rows: RegisterRow[];
  editingId: string | null;
  draft: Draft | null;
  busyId: string;
  onDraft: (patch: Partial<Draft>) => void;
  onEdit: (row: RegisterRow) => void;
  onCancel: () => void;
  onSave: (row: RegisterRow) => void;
  onDelete: (row: RegisterRow) => void;
}) {
  if (!rows.length) {
    return <p className="muted">В регистре пока нет строк.</p>;
  }
  return (
    <div className="table-wrap">
      <table className="register-table">
        <thead>
          <tr>
            <th>Контрагент</th>
            <th>Артикул</th>
            <th>Магазин</th>
            <th className="num">Количество</th>
            {kind === "sales" ? <th className="num">Цена</th> : <th>Дата</th>}
            {kind === "sales" ? <th>Период</th> : null}
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const editing = editingId === row.id && draft;
            const shop = registerShopLabel(row.shop);
            return (
              <tr key={row.id}>
                <td>{row.counterparty_name}</td>
                <td>
                  {editing ? (
                    <input
                      className="control"
                      aria-label={`Артикул ${row.counterparty_name}`}
                      value={draft.article}
                      onChange={(event) => onDraft({ article: event.target.value })}
                    />
                  ) : (
                    row.article
                  )}
                </td>
                <td>
                  {editing ? (
                    <input
                      className="control"
                      aria-label={`Магазин ${row.counterparty_name}`}
                      value={draft.shop}
                      onChange={(event) => onDraft({ shop: event.target.value })}
                    />
                  ) : (
                    shop || "—"
                  )}
                </td>
                <td className="num">
                  {editing ? (
                    <input
                      className="control"
                      aria-label={`Количество ${row.counterparty_name}`}
                      value={draft.quantity}
                      onChange={(event) => onDraft({ quantity: event.target.value })}
                    />
                  ) : (
                    row.quantity
                  )}
                </td>
                {kind === "sales" ? <td className="num">{row.price != null ? formatMoney(row.price) : "—"}</td> : <td>{row.stock_date || "—"}</td>}
                {kind === "sales" ? <td>{periodLabel(row)}</td> : null}
                <td>
                  <RowActionsMenu
                    items={
                      editing
                        ? [
                            { id: "save", label: "Сохранить", onSelect: () => onSave(row) },
                            { id: "cancel", label: "Отмена", onSelect: onCancel },
                          ]
                        : [
                            { id: "edit", label: "Изменить", onSelect: () => onEdit(row) },
                            { id: "delete", label: "Удалить", danger: true, onSelect: () => onDelete(row) },
                          ]
                    }
                  />
                  {busyId === row.id ? <span className="muted">…</span> : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function RegistersPage() {
  const [kind, setKind] = useState<RegisterKind>("sales");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [rows, setRows] = useState<RegisterRow[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ page: String(page), page_size: "50" });
    if (query) params.set("q", query);
    api<{ total: number; items: RegisterRow[] }>(`/api/v1/registers/${kind}?${params}`)
      .then((data) => {
        if (cancelled) return;
        setTotal(data.total);
        setRows(data.items);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Не удалось открыть регистр");
      });
    return () => {
      cancelled = true;
    };
  }, [kind, page, query]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setQuery(q.trim());
    setEditingId(null);
    setDraft(null);
  }

  function onEdit(row: RegisterRow) {
    setEditingId(row.id);
    setDraft(draftOf(row));
    setError("");
  }

  function onCancel() {
    setEditingId(null);
    setDraft(null);
  }

  async function onSave(row: RegisterRow) {
    if (!draft || busyId) return;
    const quantity = Number(draft.quantity.replace(",", "."));
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setError("Количество должно быть больше 0");
      return;
    }
    const shop = registerShopLabel(draft.shop);
    setError("");
    setBusyId(row.id);
    try {
      await api(`/api/v1/registers/${kind}/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ article: draft.article.trim(), quantity, shop: shop || null }),
      });
      setRows((prev) =>
        prev.map((item) => (item.id === row.id ? { ...item, article: draft.article.trim(), quantity, shop: shop || null } : item)),
      );
      setEditingId(null);
      setDraft(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить строку");
    } finally {
      setBusyId("");
    }
  }

  async function onDelete(row: RegisterRow) {
    if (busyId) return;
    if (!window.confirm(`Удалить строку ${row.article} (${row.counterparty_name})?`)) return;
    setError("");
    setBusyId(row.id);
    try {
      await api(`/api/v1/registers/${kind}/${row.id}`, { method: "DELETE" });
      setRows((prev) => prev.filter((item) => item.id !== row.id));
      setTotal((value) => Math.max(0, value - 1));
      if (editingId === row.id) onCancel();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить строку");
    } finally {
      setBusyId("");
    }
  }

  return (
    <>
      <PageHeader
        title="Регистры"
        subtitle="Загруженные продажи, остатки и доп. мотивация"
        icon="table"
        actions={
          <button
            type="button"
            className="btn secondary"
            onClick={() => downloadFile(`/api/v1/registers/${kind}.xlsx${query ? `?q=${encodeURIComponent(query)}` : ""}`, `register_${kind}.xlsx`)}
          >
            Excel
          </button>
        }
      />
      <div className="seg" role="tablist">
        {KINDS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={kind === item.id}
            className={`seg-tab ${kind === item.id ? "active" : ""}`}
            onClick={() => {
              setKind(item.id);
              setPage(1);
              onCancel();
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      <form className="toolbar" onSubmit={onSearch}>
        <label className="field">
          <span>Поиск</span>
          <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Контрагент или артикул" />
        </label>
        <button className="btn secondary" type="submit">
          Найти
        </button>
      </form>
      {error && <div className="alert">{error}</div>}
      <div className="panel">
        <RegisterTable
          kind={kind}
          rows={rows}
          editingId={editingId}
          draft={draft}
          busyId={busyId}
          onDraft={(patch) => setDraft((current) => (current ? { ...current, ...patch } : current))}
          onEdit={onEdit}
          onCancel={onCancel}
          onSave={onSave}
          onDelete={onDelete}
        />
        <Pager page={page} total={total} onChange={setPage} />
      </div>
    </>
  );
}
