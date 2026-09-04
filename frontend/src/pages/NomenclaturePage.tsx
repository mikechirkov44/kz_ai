import { useEffect, useState } from "react";
import { api, downloadFile } from "../api";
import DataTable from "../components/DataTable";
import Modal from "../components/Modal";
import PageHeader from "../components/PageHeader";
import SourceSelect from "../components/SourceSelect";
import { useODataSources } from "../odataSources";

type Nom = {
  id: string;
  article?: string;
  barcode?: string;
  name?: string;
  lts?: string;
  lts_date?: string;
  wear_type?: string;
  metal_color?: string;
  direction?: string;
  assay?: string;
  weight?: number | null;
  characteristics?: string | null;
  source_id: string;
};

export default function NomenclaturePage() {
  const { sources, labelOf } = useODataSources();
  const [q, setQ] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [items, setItems] = useState<Nom[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Nom | null>(null);

  async function load(p = page) {
    const sp = new URLSearchParams({ page: String(p), page_size: "50" });
    if (q) sp.set("q", q);
    if (sourceId) sp.set("source_id", sourceId);
    const data = await api<{ items: Nom[]; total: number }>(`/api/v1/catalogs/nomenclature?${sp}`);
    setItems(data.items);
    setTotal(data.total);
    setPage(p);
  }

  useEffect(() => {
    const t = setTimeout(() => load(1).catch(() => setItems([])), 200);
    return () => clearTimeout(t);
  }, [q, sourceId]);

  return (
    <>
      <PageHeader
        title="Номенклатура"
        subtitle="Справочник из 1С: артикул, ЖЦТ, тип, цвет"
        actions={
          <button
            className="btn secondary"
            onClick={() => {
              const sp = new URLSearchParams();
              if (q) sp.set("q", q);
              if (sourceId) sp.set("source_id", sourceId);
              downloadFile(`/api/v1/catalogs/nomenclature.xlsx?${sp}`, "nomenclature.xlsx").catch(
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
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Артикул / название" />
        </label>
        <label className="field">
          <span>База</span>
          <SourceSelect value={sourceId} onChange={setSourceId} sources={sources} />
        </label>
        <div className="field">
          <span>&nbsp;</span>
          <button className="btn" onClick={() => load(1)}>
            Обновить
          </button>
        </div>
      </div>
      <p className="muted">Всего: {total}</p>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <DataTable
          storageKey="nomenclature"
          rows={items}
          rowKey={(n) => n.id}
          onRowClick={setSelected}
          columns={[
            {
              key: "article",
              title: "Артикул",
              width: 130,
              sticky: true,
              getValue: (n) => n.article || "",
              render: (n) => n.article || "—",
            },
            {
              key: "name",
              title: "Наименование",
              width: 260,
              getValue: (n) => n.name || "",
              render: (n) => n.name || "—",
            },
            {
              key: "lts",
              title: "ЖЦТ",
              width: 110,
              getValue: (n) => n.lts || "",
              render: (n) => n.lts || "—",
            },
            {
              key: "lts_date",
              title: "Дата ЖЦТ",
              width: 120,
              getValue: (n) => n.lts_date || "",
              render: (n) => n.lts_date || "—",
            },
            {
              key: "wear_type",
              title: "Тип",
              width: 120,
              getValue: (n) => n.wear_type || "",
              render: (n) => n.wear_type || "—",
            },
            {
              key: "metal_color",
              title: "Цвет",
              width: 110,
              getValue: (n) => n.metal_color || "",
              render: (n) => n.metal_color || "—",
            },
            {
              key: "source_id",
              title: "База",
              width: 140,
              getValue: (n) => labelOf(n.source_id),
              render: (n) => labelOf(n.source_id),
            },
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
        title={selected?.article || selected?.name || "Номенклатура"}
        subtitle={selected ? labelOf(selected.source_id) : undefined}
      >
        {selected && (
          <dl className="detail-list">
            <div>
              <dt>Артикул</dt>
              <dd>{selected.article || "—"}</dd>
            </div>
            <div>
              <dt>Наименование</dt>
              <dd>{selected.name || "—"}</dd>
            </div>
            <div>
              <dt>Штрихкод</dt>
              <dd>{selected.barcode || "—"}</dd>
            </div>
            <div>
              <dt>ЖЦТ</dt>
              <dd>{selected.lts || "—"}</dd>
            </div>
            <div>
              <dt>Дата ЖЦТ</dt>
              <dd>{selected.lts_date || "—"}</dd>
            </div>
            <div>
              <dt>Тип ношения</dt>
              <dd>{selected.wear_type || "—"}</dd>
            </div>
            <div>
              <dt>Цвет металла</dt>
              <dd>{selected.metal_color || "—"}</dd>
            </div>
            <div>
              <dt>Направление</dt>
              <dd>{selected.direction || "—"}</dd>
            </div>
            <div>
              <dt>Проба</dt>
              <dd>{selected.assay || "—"}</dd>
            </div>
            <div>
              <dt>Средний вес</dt>
              <dd>{selected.weight != null ? selected.weight : "—"}</dd>
            </div>
            <div>
              <dt>Характеристики</dt>
              <dd>{selected.characteristics || "—"}</dd>
            </div>
          </dl>
        )}
      </Modal>
    </>
  );
}
