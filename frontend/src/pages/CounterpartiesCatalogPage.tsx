import { useEffect, useState } from "react";
import { api, downloadFile } from "../api";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";

type CP = {
  id: string;
  name: string;
  source_id: string;
  is_promo: boolean;
  work_type?: string;
  work_type_percent?: number;
  shops?: string[];
  region?: string;
  head_name?: string;
};

const SOURCE_OPTIONS = [
  { value: "", label: "Все" },
  { value: "asil", label: "asil" },
  { value: "miamor", label: "miamor" },
];

export default function CounterpartiesCatalogPage() {
  const [q, setQ] = useState("");
  const [sourceId, setSourceId] = useState("asil");
  const [promoOnly, setPromoOnly] = useState(false);
  const [items, setItems] = useState<CP[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<CP | null>(null);

  async function load(p = 1) {
    const sp = new URLSearchParams({ page: String(p), page_size: "50" });
    if (q) sp.set("q", q);
    if (sourceId) sp.set("source_id", sourceId);
    if (promoOnly) sp.set("promo_only", "true");
    const data = await api<{ items: CP[]; total: number }>(`/api/v1/catalogs/counterparties?${sp}`);
    setItems(data.items);
    setTotal(data.total);
    setPage(p);
  }

  useEffect(() => {
    const t = setTimeout(() => load(1).catch(() => setItems([])), 200);
    return () => clearTimeout(t);
  }, [q, sourceId, promoOnly]);

  async function open(id: string) {
    const detail = await api<CP>(`/api/v1/catalogs/counterparties/${id}`);
    setSelected(detail);
  }

  return (
    <>
      <PageHeader
        title="Контрагенты"
        subtitle="Справочник из 1С: головной, магазины, тип работы, акция"
        actions={
          <button
            className="btn secondary"
            onClick={() => {
              const sp = new URLSearchParams();
              if (q) sp.set("q", q);
              if (sourceId) sp.set("source_id", sourceId);
              if (promoOnly) sp.set("promo_only", "true");
              downloadFile(`/api/v1/catalogs/counterparties.xlsx?${sp}`, "counterparties.xlsx").catch(
                () => undefined,
              );
            }}
          >
            Excel
          </button>
        }
      />
      <div className="panel grid-3">
        <label className="field">
          <span>Поиск</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <label className="field">
          <span>База</span>
          <Select value={sourceId} onChange={setSourceId} options={SOURCE_OPTIONS} />
        </label>
        <label className="toggle" style={{ alignSelf: "end", marginBottom: 8 }}>
          <input type="checkbox" checked={promoOnly} onChange={(e) => setPromoOnly(e.target.checked)} />
          Только акция
        </label>
      </div>
      <p className="muted">Всего: {total}</p>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey="counterparties"
          rows={items}
          rowKey={(c) => c.id}
          onRowClick={(c) => open(c.id)}
          columns={[
            { key: "name", title: "Наименование", width: 240, sticky: true },
            {
              key: "work_type",
              title: "Тип работы",
              width: 130,
              getValue: (c) => c.work_type || "",
              render: (c) => c.work_type || "—",
            },
            {
              key: "work_type_percent",
              title: "%",
              width: 80,
              align: "right",
              getValue: (c) => c.work_type_percent ?? null,
              render: (c) => c.work_type_percent ?? "—",
            },
            {
              key: "is_promo",
              title: "Акция",
              width: 90,
              getValue: (c) => (c.is_promo ? 1 : 0),
              render: (c) => (c.is_promo ? "да" : "нет"),
            },
            {
              key: "shops",
              title: "Магазины",
              width: 220,
              getValue: (c) => (c.shops || []).join(", "),
              render: (c) => (c.shops || []).slice(0, 3).join(", ") || "—",
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
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.name || "Контрагент"}
        subtitle={selected?.source_id}
      >
        {selected && (
          <dl className="detail-list">
            <div>
              <dt>Головной</dt>
              <dd>{selected.head_name || "—"}</dd>
            </div>
            <div>
              <dt>Регион</dt>
              <dd>{selected.region || "—"}</dd>
            </div>
            <div>
              <dt>Тип работы</dt>
              <dd>{selected.work_type || "—"}</dd>
            </div>
            <div>
              <dt>%</dt>
              <dd>{selected.work_type_percent ?? "—"}</dd>
            </div>
            <div>
              <dt>Акция</dt>
              <dd>{selected.is_promo ? "да" : "нет"}</dd>
            </div>
            <div>
              <dt>Магазины</dt>
              <dd>{(selected.shops || []).join(", ") || "—"}</dd>
            </div>
          </dl>
        )}
      </Modal>
    </>
  );
}
