import { useEffect, useState } from "react";
import { api, downloadFile } from "../api";
import Checkbox from "../components/Checkbox";
import DataTable from "../components/DataTable";
import { ExcelLabel } from "../components/ExcelIcon";
import Modal from "../components/Modal";
import Pager from "../components/Pager";
import PageHeader from "../components/PageHeader";
import SourceSelect from "../components/SourceSelect";
import {
  counterpartyMainRows,
  counterpartyOtherRows,
  counterpartyRequisiteRows,
  extraPropertyRows,
} from "../counterpartyDetails";
import { visibleDetailRows } from "../nomenclatureDetails";
import { useODataSources } from "../odataSources";
import { formatWorkTypePercent, workTypeLabel } from "../workType";

type CP = {
  id: string;
  name: string;
  source_id: string;
  is_promo: boolean;
  work_type?: string;
  work_type_label?: string;
  work_type_percent?: number;
  shops?: string[];
  region?: string;
  head_name?: string;
  parent_name?: string;
  manager_name?: string | null;
  code?: string | null;
  full_name?: string | null;
  legal_status?: string | null;
  is_buyer?: boolean;
  is_supplier?: boolean;
  iin?: string | null;
  identity_document?: string | null;
  rnn?: string | null;
  sik?: string | null;
  okpo?: string | null;
  kbe?: string | null;
  work_schedule?: string | null;
  comment?: string | null;
  director_name?: string | null;
  extra_properties?: Record<string, string> | null;
};

export default function CounterpartiesCatalogPage() {
  const { sources, labelOf } = useODataSources();
  const [q, setQ] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [promoOnly, setPromoOnly] = useState(false);
  const [items, setItems] = useState<CP[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<CP | null>(null);
  const [loading, setLoading] = useState(true);

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
    setLoading(true);
    const t = setTimeout(() => {
      load(1)
        .catch(() => {
          setItems([]);
          setTotal(0);
        })
        .finally(() => setLoading(false));
    }, 200);
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
        subtitle="Справочник из 1С"
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
            <ExcelLabel>Excel</ExcelLabel>
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
          <SourceSelect value={sourceId} onChange={setSourceId} sources={sources} />
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
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey="counterparties"
          rows={items}
          rowKey={(c) => c.id}
          onRowClick={(c) => open(c.id)}
          loading={loading}
          columns={[
            { key: "name", title: "Наименование", width: 240, sticky: true },
            {
              key: "work_type",
              title: "Тип работы",
              width: 130,
              getValue: (c) => workTypeLabel(c.work_type_label || c.work_type),
              render: (c) => workTypeLabel(c.work_type_label || c.work_type),
            },
            {
              key: "work_type_percent",
              title: "% типа работы",
              width: 130,
              align: "right",
              getValue: (c) => c.work_type_percent ?? null,
              render: (c) => formatWorkTypePercent(c.work_type_percent),
            },
            {
              key: "is_promo",
              title: "Акция",
              width: 90,
              getValue: (c) => (c.is_promo ? 1 : 0),
              render: (c) => (c.is_promo ? "да" : "нет"),
            },
            {
              key: "manager_name",
              title: "Менеджер",
              width: 160,
              getValue: (c) => c.manager_name || "",
              render: (c) => c.manager_name || "—",
            },
            {
              key: "shops",
              title: "Магазины",
              width: 220,
              getValue: (c) => (c.shops || []).join(", "),
              render: (c) => (c.shops || []).slice(0, 3).join(", ") || "—",
            },
            {
              key: "source_id",
              title: "База",
              width: 140,
              getValue: (c) => labelOf(c.source_id),
              render: (c) => labelOf(c.source_id),
            },
          ]}
        />
      </div>
      <Pager page={page} total={total} disabled={loading} onChange={(p) => void load(p)} />

      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected?.name || "Контрагент"}
        subtitle={selected ? labelOf(selected.source_id) : undefined}
        wide
      >
        {selected && <CounterpartyDetails item={selected} />}
      </Modal>
    </>
  );
}

function DetailGroup({ title, rows }: { title: string; rows: { label: string; text: string }[] }) {
  if (!rows.length) return null;
  return (
    <section className="detail-group">
      <h3>{title}</h3>
      <dl className="detail-list">
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.text}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function CounterpartyDetails({ item }: { item: CP }) {
  return (
    <div className="detail-groups">
      <DetailGroup title="Основные" rows={visibleDetailRows(counterpartyMainRows(item))} />
      <DetailGroup title="Реквизиты" rows={visibleDetailRows(counterpartyRequisiteRows(item))} />
      <DetailGroup title="Прочее" rows={visibleDetailRows(counterpartyOtherRows(item))} />
      <DetailGroup title="Доп. сведения" rows={extraPropertyRows(item.extra_properties)} />
      <DetailGroup
        title="В сервисе"
        rows={visibleDetailRows([
          { label: "Головной", value: item.head_name },
          { label: "Регион", value: item.region },
          { label: "Тип работы", value: workTypeLabel(item.work_type_label || item.work_type) },
          { label: "% типа работы", value: formatWorkTypePercent(item.work_type_percent) },
          { label: "Акция", value: Boolean(item.is_promo), always: true },
          { label: "Менеджер", value: item.manager_name || "из 1С не указан", always: true },
        ])}
      />
    </div>
  );
}
