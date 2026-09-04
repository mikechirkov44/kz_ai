import { useEffect, useState } from "react";
import { api, formatMoney } from "../api";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import PeriodPicker from "../components/PeriodPicker";
import SourceSelect from "../components/SourceSelect";
import { documentTotalQuantity, docTypeLabel } from "../documents";
import { quarterRange } from "../months";
import { useODataSources } from "../odataSources";

type DocRow = {
  source_id: string;
  onec_ref: string;
  doc_number?: string;
  doc_date?: string;
  counterparty?: string;
  lines: number;
  quantity?: number;
  amount?: number;
};

type DocDetail = {
  type: string;
  doc_number?: string;
  doc_date?: string;
  counterparty?: string;
  warehouse?: string;
  total_amount?: number;
  total_quantity?: number;
  lines: {
    line_number: number;
    article?: string;
    name?: string;
    quantity?: number;
    price?: number;
    amount?: number;
    series?: string;
  }[];
};

const TABS = [
  { id: "realizations", label: "Реализации" },
  { id: "returns", label: "Возвраты" },
  { id: "orders", label: "Заказы" },
  { id: "production", label: "Производство" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function defaultRange(): { from: string; to: string } {
  return quarterRange(2023, 1);
}

export default function DocumentsPage() {
  const { sources, labelOf } = useODataSources();
  const [tab, setTab] = useState<TabId>("realizations");
  const initial = defaultRange();
  const [dateFrom, setDateFrom] = useState(initial.from);
  const [dateTo, setDateTo] = useState(initial.to);
  const [sourceId, setSourceId] = useState("");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<DocRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<DocDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load(p = 1, override?: { tab?: TabId; from?: string; to?: string }) {
    const activeTab = override?.tab ?? tab;
    const from = override?.from ?? dateFrom;
    const to = override?.to ?? dateTo;
    setError("");
    setDetail(null);
    setLoading(true);
    const sp = new URLSearchParams({
      page: String(p),
      page_size: "50",
      date_from: from,
      date_to: to,
    });
    if (sourceId) sp.set("source_id", sourceId);
    if (q.trim()) sp.set("q", q.trim());
    try {
      const data = await api<{ items: DocRow[]; total: number }>(`/api/v1/documents/${activeTab}?${sp}`);
      setItems(data.items);
      setTotal(data.total);
      setPage(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const t = setTimeout(() => load(1), 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, dateFrom, dateTo, sourceId, q]);

  function switchTab(next: TabId) {
    const range = defaultRange();
    setTab(next);
    setDateFrom(range.from);
    setDateTo(range.to);
    setItems([]);
    setDetail(null);
  }

  async function openDoc(row: DocRow) {
    const data = await api<DocDetail>(`/api/v1/documents/${tab}/${row.source_id}/${row.onec_ref}`);
    setDetail(data);
  }

  const emptyHint = "Нет документов за период — смените период или вкладку";

  const totalQty = detail ? documentTotalQuantity(detail.total_quantity, detail.lines) : 0;

  return (
    <>
      <PageHeader
        title="Журнал документов"
        subtitle="Документы из 1С — фильтры и просмотр строк в окне"
        actions={
          <button className="btn" onClick={() => load(1)} disabled={loading}>
            {loading ? "Загрузка…" : "Обновить"}
          </button>
        }
      />

      <div className="seg-tabs" role="tablist" aria-label="Тип документа">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`seg-tab ${tab === t.id ? "active" : ""}`}
            onClick={() => switchTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="panel filters-bar grid-3">
        <PeriodPicker
          from={dateFrom}
          to={dateTo}
          mode="range"
          minYear={2023}
          onChange={(nextFrom, nextTo) => {
            setDateFrom(nextFrom);
            setDateTo(nextTo);
          }}
        />
        <label className="field">
          <span>Поиск</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={tab === "production" ? "Ссылка 1С, серия…" : "Номер, контрагент, склад…"}
          />
        </label>
        <label className="field">
          <span>База</span>
          <SourceSelect value={sourceId} onChange={setSourceId} sources={sources} />
        </label>
      </div>
      {error && <div className="alert">{error}</div>}
      <p className="muted">
        Найдено документов: {total}
        {loading ? " · обновляем…" : ""}
      </p>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey={`documents-${tab}`}
          rows={items}
          rowKey={(r) => `${r.source_id}-${r.onec_ref}`}
          onRowClick={openDoc}
          empty={emptyHint}
          columns={[
            {
              key: "doc_date",
              title: "Дата",
              width: 120,
              getValue: (r) => r.doc_date || "",
              render: (r) => r.doc_date || "—",
            },
            {
              key: "doc_number",
              title: "Номер",
              width: 140,
              getValue: (r) => r.doc_number || r.onec_ref,
              render: (r) => r.doc_number || r.onec_ref.slice(0, 8),
            },
            {
              key: "counterparty",
              title: "Контрагент",
              width: 220,
              sticky: true,
              getValue: (r) => r.counterparty || "",
              render: (r) => r.counterparty || "—",
            },
            { key: "lines", title: "Строк", width: 90, align: "right" },
            {
              key: "quantity",
              title: "Кол-во",
              width: 110,
              align: "right",
              getValue: (r) => r.quantity ?? null,
              render: (r) => (r.quantity != null ? formatMoney(r.quantity) : "—"),
            },
            {
              key: "amount",
              title: "Сумма",
              width: 120,
              align: "right",
              getValue: (r) => r.amount ?? null,
              render: (r) => (r.amount != null ? formatMoney(r.amount) : "—"),
            },
            {
              key: "source_id",
              title: "База",
              width: 140,
              getValue: (r) => labelOf(r.source_id),
              render: (r) => labelOf(r.source_id),
            },
          ]}
        />
      </div>
      <div className="toolbar">
        <button className="btn secondary" disabled={page <= 1 || loading} onClick={() => load(page - 1)}>
          ←
        </button>
        <span className="pill">стр. {page}</span>
        <button
          className="btn secondary"
          disabled={items.length < 50 || loading}
          onClick={() => load(page + 1)}
        >
          →
        </button>
      </div>

      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        wide
        title={`${docTypeLabel(detail?.type)}${detail?.doc_number ? ` · ${detail.doc_number}` : ""}`}
        subtitle={`${detail?.doc_date || ""} · ${detail?.counterparty || ""}`}
      >
        {detail && (
          <>
            {(detail.total_amount != null || totalQty > 0) && (
              <p>
                Итого
                {detail.total_amount != null ? `: ${formatMoney(detail.total_amount)} тг` : ""}
                {` · ${formatMoney(totalQty)} шт`}
              </p>
            )}
            {!!detail.lines?.length && (
              <DataTable
                storageKey="document-lines"
                maxHeight="50vh"
                rows={detail.lines}
                rowKey={(l) => String(l.line_number)}
                columns={[
                  { key: "line_number", title: "#", width: 60, align: "right" },
                  {
                    key: "article",
                    title: "Артикул",
                    width: 120,
                    getValue: (l) => l.article || "",
                    render: (l) => l.article || "—",
                  },
                  {
                    key: "name",
                    title: "Наименование",
                    width: 240,
                    getValue: (l) => l.name || "",
                    render: (l) => l.name || "—",
                  },
                  {
                    key: "quantity",
                    title: "Кол-во",
                    width: 100,
                    align: "right",
                    getValue: (l) => l.quantity ?? null,
                    render: (l) => (l.quantity != null ? formatMoney(l.quantity) : "—"),
                  },
                  {
                    key: "price",
                    title: "Цена",
                    width: 100,
                    align: "right",
                    getValue: (l) => l.price ?? null,
                    render: (l) => (l.price != null ? formatMoney(l.price) : "—"),
                  },
                  {
                    key: "amount",
                    title: "Сумма",
                    width: 110,
                    align: "right",
                    getValue: (l) => l.amount ?? null,
                    render: (l) => (l.amount != null ? formatMoney(l.amount) : "—"),
                  },
                ]}
              />
            )}
          </>
        )}
      </Modal>
    </>
  );
}
