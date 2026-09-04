import { useEffect, useState } from "react";
import { api, formatMoney } from "../api";
import DataTable from "../components/DataTable";
import DatePicker from "../components/DatePicker";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";

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

export default function DocumentsPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("realizations");
  const [dateFrom, setDateFrom] = useState("2023-01-01");
  const [dateTo, setDateTo] = useState("2023-03-31");
  const [sourceId, setSourceId] = useState("asil");
  const [items, setItems] = useState<DocRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<DocDetail | null>(null);
  const [error, setError] = useState("");

  async function load(p = 1) {
    setError("");
    setDetail(null);
    const sp = new URLSearchParams({
      page: String(p),
      page_size: "50",
      date_from: dateFrom,
      date_to: dateTo,
    });
    if (sourceId) sp.set("source_id", sourceId);
    try {
      const data = await api<{ items: DocRow[]; total: number }>(`/api/v1/documents/${tab}?${sp}`);
      setItems(data.items);
      setTotal(data.total);
      setPage(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
      setItems([]);
    }
  }

  useEffect(() => {
    load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function openDoc(row: DocRow) {
    const data = await api<DocDetail>(`/api/v1/documents/${tab}/${row.source_id}/${row.onec_ref}`);
    setDetail(data);
  }

  return (
    <>
      <PageHeader
        title="Журнал документов"
        subtitle="Документы из 1С — фильтры и просмотр строк в окне"
        actions={
          <button className="btn" onClick={() => load(1)}>
            Обновить
          </button>
        }
      />
      <div className="toolbar" style={{ marginBottom: 14 }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`btn ${tab === t.id ? "" : "secondary"}`}
            onClick={() => {
              setTab(t.id);
              setItems([]);
              setDetail(null);
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="panel grid-3">
        <label className="field">
          <span>С даты</span>
          <DatePicker value={dateFrom} onChange={setDateFrom} />
        </label>
        <label className="field">
          <span>По дату</span>
          <DatePicker value={dateTo} onChange={setDateTo} />
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
      </div>
      {error && <div className="alert">{error}</div>}
      <p className="muted">Найдено документов: {total}</p>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey="documents"
          rows={items}
          rowKey={(r) => `${r.source_id}-${r.onec_ref}`}
          onRowClick={openDoc}
          empty="Нет документов за период — смените даты или вкладку"
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
            { key: "source_id", title: "База", width: 90 },
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

      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        wide
        title={`${detail?.type || ""} · ${detail?.doc_number || ""}`}
        subtitle={`${detail?.doc_date || ""} · ${detail?.counterparty || ""}`}
      >
        {detail && (
          <>
            {detail.total_amount != null && (
              <p>
                Итого: {formatMoney(detail.total_amount)} тг · {formatMoney(detail.total_quantity || 0)} шт
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
