import { FormEvent, useEffect, useState } from "react";
import { api, downloadFile, formatMoney } from "../api";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import Pager from "../components/Pager";

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

type Draft = { article: string; shop: string; quantity: string; price: string };

export function registerShopLabel(shop?: string | null): string {
  const text = (shop ?? "").trim();
  if (!text || EMPTY_SHOP.has(text.toLowerCase())) return "";
  return text;
}

function draftOf(row: RegisterRow): Draft {
  return {
    article: row.article,
    shop: registerShopLabel(row.shop),
    quantity: String(row.quantity),
    price: row.price != null ? String(row.price) : "",
  };
}

function parseAmount(raw: string): number {
  return Number(raw.replace(/\s/g, "").replace(",", "."));
}

function periodLabel(row: RegisterRow): string {
  if (row.period_year && row.period_month) {
    return `${row.period_year}-${String(row.period_month).padStart(2, "0")}`;
  }
  return "—";
}

export function RegisterLineCard({
  kind,
  row,
  busy,
  onSave,
  onDelete,
}: {
  kind: RegisterKind;
  row: RegisterRow;
  busy: boolean;
  onSave: (draft: Draft) => void;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => draftOf(row));

  useEffect(() => {
    setDraft(draftOf(row));
  }, [row]);

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSave(draft);
      }}
    >
      <div className="grid-2">
        <label className="field">
          <span>Контрагент</span>
          <input className="control" value={row.counterparty_name} readOnly />
        </label>
        <label className="field">
          <span>Артикул</span>
          <input
            className="control"
            aria-label="Артикул"
            value={draft.article}
            onChange={(event) => setDraft((current) => ({ ...current, article: event.target.value }))}
          />
        </label>
        <label className="field">
          <span>Магазин</span>
          <input
            className="control"
            aria-label="Магазин"
            value={draft.shop}
            onChange={(event) => setDraft((current) => ({ ...current, shop: event.target.value }))}
          />
        </label>
        <label className="field">
          <span>Количество</span>
          <input
            className="control"
            aria-label="Количество"
            value={draft.quantity}
            onChange={(event) => setDraft((current) => ({ ...current, quantity: event.target.value }))}
          />
        </label>
        {kind === "sales" ? (
          <label className="field">
            <span>Цена</span>
            <input
              className="control"
              aria-label="Цена"
              inputMode="decimal"
              value={draft.price}
              onChange={(event) => setDraft((current) => ({ ...current, price: event.target.value }))}
            />
          </label>
        ) : (
          <label className="field">
            <span>Дата</span>
            <input className="control" value={row.stock_date || "—"} readOnly />
          </label>
        )}
        {kind === "sales" ? (
          <label className="field">
            <span>Период</span>
            <input className="control" value={periodLabel(row)} readOnly />
          </label>
        ) : null}
      </div>
      <div className="toolbar" style={{ marginTop: 12 }}>
        <button className="btn" type="submit" disabled={busy}>
          Сохранить
        </button>
        <button className="btn danger" type="button" disabled={busy} onClick={onDelete}>
          Удалить
        </button>
      </div>
    </form>
  );
}

export function RegisterTable({
  kind,
  rows,
  onOpen,
}: {
  kind: RegisterKind;
  rows: RegisterRow[];
  onOpen: (row: RegisterRow) => void;
}) {
  const sales = kind === "sales";
  return (
    <DataTable
      storageKey={`registers-${kind}`}
      rows={rows}
      rowKey={(row) => row.id}
      onRowClick={onOpen}
      empty="В регистре пока нет строк."
      columns={[
        {
          key: "counterparty",
          title: "Контрагент",
          width: 220,
          sticky: true,
          getValue: (row) => row.counterparty_name,
        },
        {
          key: "article",
          title: "Артикул",
          width: 140,
          getValue: (row) => row.article,
        },
        {
          key: "shop",
          title: "Магазин",
          width: 160,
          getValue: (row) => registerShopLabel(row.shop),
          render: (row) => registerShopLabel(row.shop) || "—",
        },
        {
          key: "quantity",
          title: "Количество",
          width: 120,
          align: "right",
          getValue: (row) => row.quantity,
        },
        sales
          ? {
              key: "price",
              title: "Цена",
              width: 120,
              align: "right" as const,
              getValue: (row: RegisterRow) => row.price ?? null,
              render: (row: RegisterRow) => (row.price != null ? formatMoney(row.price) : "—"),
            }
          : {
              key: "stock_date",
              title: "Дата",
              width: 120,
              getValue: (row: RegisterRow) => row.stock_date || "",
              render: (row: RegisterRow) => row.stock_date || "—",
            },
        ...(sales
          ? [
              {
                key: "period",
                title: "Период",
                width: 110,
                getValue: (row: RegisterRow) =>
                  row.period_year && row.period_month ? row.period_year * 100 + row.period_month : null,
                render: (row: RegisterRow) => periodLabel(row),
              },
            ]
          : []),
      ]}
    />
  );
}

export default function RegistersPage() {
  const [kind, setKind] = useState<RegisterKind>("sales");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [rows, setRows] = useState<RegisterRow[]>([]);
  const [selected, setSelected] = useState<RegisterRow | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
  }

  async function onSave(draft: Draft) {
    if (!selected || busy) return;
    const quantity = parseAmount(draft.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setError("Количество должно быть больше 0");
      return;
    }
    let price: number | null = selected.price ?? null;
    if (kind === "sales") {
      price = parseAmount(draft.price);
      if (!Number.isFinite(price) || price <= 0) {
        setError("Цена должна быть больше 0");
        return;
      }
    }
    const shop = registerShopLabel(draft.shop);
    const article = draft.article.trim();
    setError("");
    setBusy(true);
    try {
      const body: Record<string, string | number | null> = { article, quantity, shop: shop || null };
      if (kind === "sales") body.price = price;
      await api(`/api/v1/registers/${kind}/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      const next = { ...selected, article, quantity, shop: shop || null, ...(kind === "sales" ? { price } : {}) };
      setRows((prev) => prev.map((item) => (item.id === selected.id ? next : item)));
      setSelected(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить строку");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!selected || busy) return;
    if (!window.confirm(`Удалить строку ${selected.article} (${selected.counterparty_name})?`)) return;
    setError("");
    setBusy(true);
    try {
      await api(`/api/v1/registers/${kind}/${selected.id}`, { method: "DELETE" });
      setRows((prev) => prev.filter((item) => item.id !== selected.id));
      setTotal((value) => Math.max(0, value - 1));
      setSelected(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить строку");
    } finally {
      setBusy(false);
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
            onClick={() =>
              downloadFile(
                `/api/v1/registers/${kind}.xlsx${query ? `?q=${encodeURIComponent(query)}` : ""}`,
                `register_${kind}.xlsx`,
              )
            }
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
              setSelected(null);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      <form className="register-search" onSubmit={onSearch}>
        <input
          aria-label="Поиск"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="Контрагент или артикул"
        />
        <button className="btn secondary" type="submit">
          Найти
        </button>
      </form>
      {error && <div className="alert">{error}</div>}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <RegisterTable kind={kind} rows={rows} onOpen={setSelected} />
      </div>
      <Pager page={page} total={total} onChange={setPage} />
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.counterparty_name || "Строка"}
        subtitle={selected?.article}
      >
        {selected ? (
          <RegisterLineCard kind={kind} row={selected} busy={busy} onSave={onSave} onDelete={onDelete} />
        ) : null}
      </Modal>
    </>
  );
}
