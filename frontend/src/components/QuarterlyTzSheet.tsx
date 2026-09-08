import { useMemo, useState } from "react";
import { filterQuarterlyClients, uniqueManagers, uniqueWorkTypes } from "../quarterlyFilters";
import type { DimMetrics, MatrixRow, RecItem, SummaryClient, SummaryLabels } from "./QuarterlyMatrix";
import { RecList } from "./QuarterlyMatrix";
import Select from "./Select";

function qty(value: number | null | undefined): string {
  if (value == null) return "";
  return Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
}

function pct(value: number | null | undefined): string {
  if (value == null) return "";
  return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
}

function signedQty(value: number | null | undefined): string {
  if (value == null) return "";
  const n = Number(value);
  const abs = Math.abs(n).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
  if (n > 0) return `+${abs}`;
  if (n < 0) return `−${abs}`;
  return abs;
}

function dynQtyClass(value: number | null | undefined): string {
  if (value == null || Number(value) === 0) return "";
  return Number(value) > 0 ? "dyn-up" : "dyn-down";
}

function cell(row: MatrixRow | undefined, key: "metal_color" | "lts" | "wear_type"): DimMetrics | null {
  return row?.[key] || null;
}

function DimTds({ dim }: { dim: DimMetrics | null }) {
  if (!dim) {
    return (
      <>
        <td />
        <td className="num" />
        <td className="num" />
        <td className="num" />
        <td className="num" />
      </>
    );
  }
  return (
    <>
      <td>{dim.dimension}</td>
      <td className="num">{qty(dim.avg_stock)}</td>
      <td className="num">{qty(dim.sales_total)}</td>
      <td className="num">{pct(dim.quarter_turnover_percent)}</td>
      <td className="num">{pct(dim.avg_month_turnover_percent)}</td>
    </>
  );
}

type Props = {
  year: number;
  quarter: number;
  labels?: SummaryLabels;
  clients: SummaryClient[];
  includeEmpty?: boolean;
  onIncludeEmptyChange?: (value: boolean) => void;
  query?: string;
  onQueryChange?: (value: string) => void;
  workType?: string;
  onWorkTypeChange?: (value: string) => void;
  manager?: string;
  onManagerChange?: (value: string) => void;
  onSaveComment?: (counterpartyId: string, text: string) => Promise<void>;
  onShowHistory?: (counterpartyId: string) => void;
};

export default function QuarterlyTzSheet({
  year,
  quarter,
  labels = {},
  clients,
  includeEmpty = false,
  onIncludeEmptyChange,
  query = "",
  onQueryChange,
  workType = "",
  onWorkTypeChange,
  manager = "",
  onManagerChange,
  onSaveComment,
  onShowHistory,
}: Props) {
  const [openIds, setOpenIds] = useState<Record<string, boolean>>({});
  const [managerSearch, setManagerSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState("");

  const workTypeOptions = useMemo(
    () => [
      { value: "", label: "Все типы работы" },
      ...uniqueWorkTypes(clients).map((item) => ({ value: item, label: item })),
    ],
    [clients],
  );
  const managerOptions = useMemo(() => {
    const needle = managerSearch.trim().toLowerCase();
    const names = uniqueManagers(clients).filter((name) => !needle || name.toLowerCase().includes(needle));
    return [{ value: "", label: "Все менеджеры" }, ...names.map((item) => ({ value: item, label: item }))];
  }, [clients, managerSearch]);
  const filtered = useMemo(
    () => filterQuarterlyClients(clients, { query, workType, manager, includeEmpty: true }),
    [clients, query, workType, manager],
  );

  const allOpen = filtered.length > 0 && filtered.every((c) => openIds[c.counterparty_id]);

  function setAll(open: boolean) {
    const next: Record<string, boolean> = {};
    for (const client of filtered) next[client.counterparty_id] = open;
    setOpenIds(next);
  }

  async function save(id: string) {
    if (!onSaveComment) return;
    const text = (drafts[id] ?? "").trim();
    if (!text) return;
    setSaving(id);
    try {
      await onSaveComment(id, text);
      setDrafts((prev) => ({ ...prev, [id]: "" }));
    } finally {
      setSaving("");
    }
  }

  const metricHeads = [
    "категория",
    "ср остаток на квартал",
    labels.sales || "итого продажи",
    labels.turnover || "Об-ть квартала",
    labels.avg_turnover || "Ср. об-ть за квартал",
  ];

  return (
    <div className="tz-scroll">
      <div className="tz-filters no-print">
        <input
          className="control"
          placeholder="Контрагент…"
          value={query}
          onChange={(e) => onQueryChange?.(e.target.value)}
        />
        <div className="tz-filter-select">
          <Select
            value={workType}
            onChange={(value) => onWorkTypeChange?.(value)}
            options={workTypeOptions}
            placeholder="Все типы работы"
          />
        </div>
        <div className="tz-filter-select">
          <Select
            value={manager}
            onChange={(value) => {
              onManagerChange?.(value);
              setManagerSearch("");
            }}
            options={managerOptions}
            placeholder="Все менеджеры"
            search={managerSearch}
            onSearch={setManagerSearch}
            searchPlaceholder="Найти менеджера"
          />
        </div>
        <label className="tz-check">
          <input
            type="checkbox"
            checked={includeEmpty}
            onChange={(e) => onIncludeEmptyChange?.(e.target.checked)}
          />
          Показать всех с отгрузкой 1С
        </label>
        <button className="btn secondary sm" type="button" onClick={() => setAll(!allOpen)}>
          {allOpen ? "Свернуть все" : "Развернуть все"}
        </button>
        <span className="muted">
          {filtered.length} из {clients.length}
        </span>
      </div>
      <table className="tz-sheet">
        <thead>
          <tr>
            <th rowSpan={2}>Контрагент</th>
            <th rowSpan={2}>Тип работы контрагента</th>
            <th rowSpan={2}>% типа работ</th>
            <th rowSpan={2}>{labels.plan || "План отгрузки"}</th>
            <th colSpan={5} className="blk-metal">
              Цвет металла
            </th>
            <th colSpan={5} className="blk-lts">
              ЖЦТ
            </th>
            <th colSpan={5} className="blk-wear">
              Тип изделия
            </th>
            <th rowSpan={2}>{labels.sales_prev || "продажи пред. кв."}</th>
            <th rowSpan={2}>{labels.sales_prev2 || "продажи предпред. кв."}</th>
            <th rowSpan={2}>{labels.dynamics || "Динамика"}</th>
            <th rowSpan={2}>Комментарий</th>
            <th rowSpan={2}>{labels.next_plan || "План след. кв (шт)"}</th>
            <th rowSpan={2}>Рекомендации</th>
          </tr>
          <tr>
            {[0, 1, 2].flatMap((block) =>
              metricHeads.map((title) => (
                <th key={`${block}-${title}`}>{title}</th>
              )),
            )}
          </tr>
        </thead>
        <tbody>
          {!filtered.length && (
            <tr>
              <td colSpan={25}>Нет клиентов с продажами за {year} Q{quarter}</td>
            </tr>
          )}
          {filtered.map((client) => {
            const body = (client.matrix || []).filter((row) => !row.is_total);
            const total = (client.matrix || []).find((row) => row.is_total);
            const open = Boolean(openIds[client.counterparty_id]);
            return (
              <ClientBlock
                key={client.counterparty_id}
                client={client}
                body={body}
                total={total}
                open={open}
                onToggle={() =>
                  setOpenIds((prev) => ({ ...prev, [client.counterparty_id]: !prev[client.counterparty_id] }))
                }
                draft={drafts[client.counterparty_id] ?? ""}
                saving={saving === client.counterparty_id}
                onDraftChange={(value) => setDrafts((prev) => ({ ...prev, [client.counterparty_id]: value }))}
                onSave={() => {
                  void save(client.counterparty_id);
                }}
                onSaveComment={onSaveComment}
                onShowHistory={onShowHistory}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ClientBlock({
  client,
  body,
  total,
  open,
  onToggle,
  draft,
  saving,
  onDraftChange,
  onSave,
  onSaveComment,
  onShowHistory,
}: {
  client: SummaryClient;
  body: MatrixRow[];
  total?: MatrixRow;
  open: boolean;
  onToggle: () => void;
  draft: string;
  saving: boolean;
  onDraftChange: (value: string) => void;
  onSave: () => void;
  onSaveComment?: (counterpartyId: string, text: string) => Promise<void>;
  onShowHistory?: (counterpartyId: string) => void;
}) {
  const visibleBody = open ? body : [];
  const span = visibleBody.length + (total ? 1 : 0) || 1;
  return (
    <>
      {visibleBody.map((row, idx) => (
        <tr key={`${client.counterparty_id}-r-${idx}`}>
          {idx === 0 && <IdentityCells client={client} span={span} open={open} onToggle={onToggle} canToggle={body.length > 0} />}
          <DimTds dim={cell(row, "metal_color")} />
          <DimTds dim={cell(row, "lts")} />
          <DimTds dim={cell(row, "wear_type")} />
          <td />
          <td />
          <td />
          <td />
          <td />
          <td />
        </tr>
      ))}
      {total && (
        <tr className="tz-total">
          {(visibleBody.length === 0) && (
            <IdentityCells client={client} span={1} open={open} onToggle={onToggle} canToggle={body.length > 0} />
          )}
          <DimTds dim={cell(total, "metal_color")} />
          <DimTds dim={cell(total, "lts")} />
          <DimTds dim={cell(total, "wear_type")} />
          <td className="num">{qty(client.sales_prev_quarter)}</td>
          <td className="num">{qty(client.sales_prev2_quarter)}</td>
          <td className={`num ${dynQtyClass(client.dynamics_qty)}`}>{signedQty(client.dynamics_qty)}</td>
          <td className="tz-comment">
            {client.comment ? (
              <p className="tz-comment-text">{client.comment}</p>
            ) : onSaveComment ? (
              <p className="tz-comment-empty no-print">Нет комментария</p>
            ) : null}
            {onSaveComment && (
              <div className="tz-comment-edit no-print">
                <textarea
                  className="control"
                  rows={2}
                  placeholder="Новый комментарий"
                  value={draft}
                  onChange={(e) => onDraftChange(e.target.value)}
                />
                <div className="tz-comment-actions">
                  <button className="btn sm" type="button" disabled={saving || !draft.trim()} onClick={onSave}>
                    {saving ? "…" : "Сохранить"}
                  </button>
                  {onShowHistory && (
                    <button
                      className="btn secondary sm"
                      type="button"
                      onClick={() => onShowHistory(client.counterparty_id)}
                    >
                      История
                    </button>
                  )}
                </div>
              </div>
            )}
          </td>
          <td className="num">{qty(client.next_quarter_plan)}</td>
          <td className="tz-recs" title={client.recommendations_text || undefined}>
            <RecsCell items={client.recommendations} fallback={client.recommendations_text} />
          </td>
        </tr>
      )}
      <tr className="tz-gap">
        <td colSpan={25} />
      </tr>
    </>
  );
}

function RecsCell({ items, fallback }: { items?: RecItem[]; fallback?: string }) {
  if (items?.length) {
    return <RecList items={items} preview={null} empty="" />;
  }
  if (fallback) {
    return <span>{fallback}</span>;
  }
  return null;
}

function IdentityCells({
  client,
  span,
  open,
  onToggle,
  canToggle,
}: {
  client: SummaryClient;
  span: number;
  open: boolean;
  onToggle: () => void;
  canToggle: boolean;
}) {
  return (
    <>
      <td rowSpan={span} className="tz-name">
        {canToggle ? (
          <button type="button" className="tz-fold no-print" onClick={onToggle} aria-expanded={open}>
            {open ? "▼" : "▶"}
          </button>
        ) : null}
        {client.counterparty}
      </td>
      <td rowSpan={span}>{client.work_type_label || ""}</td>
      <td rowSpan={span} className="num">
        {qty(client.work_type_percent)}
      </td>
      <td rowSpan={span} className="num">
        {qty(client.plan)}
      </td>
    </>
  );
}
