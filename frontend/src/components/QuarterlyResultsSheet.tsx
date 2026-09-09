import { useMemo, useState } from "react";
import Select from "./Select";
import { pct, qty } from "./QuarterlyMatrix";
import CommentCell from "./CommentCell";
import TzScrollPane from "./TzScrollPane";
import {
  filterResultsClients,
  uniqueManagers,
  uniqueWorkTypes,
  type ResultsClient,
  type ResultsLabels,
} from "../quarterlyFilters";
import { formatWorkTypePercent, workTypeLabel } from "../workType";

function dynPctClass(value: number | null | undefined): string {
  if (value == null) return "";
  if (Number(value) > 100) return "dyn-up";
  if (Number(value) < 100) return "dyn-down";
  return "";
}

type Props = {
  year: number;
  quarter: number;
  labels?: ResultsLabels;
  clients: ResultsClient[];
  query?: string;
  onQueryChange?: (value: string) => void;
  workType?: string;
  onWorkTypeChange?: (value: string) => void;
  manager?: string;
  onManagerChange?: (value: string) => void;
  onSaveComment?: (counterpartyId: string, text: string) => Promise<void>;
  onShowHistory?: (counterpartyId: string) => void;
};

export default function QuarterlyResultsSheet({
  year,
  quarter,
  labels = {},
  clients,
  query = "",
  onQueryChange,
  workType = "",
  onWorkTypeChange,
  manager = "",
  onManagerChange,
  onSaveComment,
  onShowHistory,
}: Props) {
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
    () => filterResultsClients(clients, { query, workType, manager }),
    [clients, query, workType, manager],
  );

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

  return (
    <div className="tz-sheet-wrap">
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
        <span className="muted">
          {filtered.length} из {clients.length}
        </span>
      </div>
      <TzScrollPane deps={[filtered.length, clients.length]}>
      <table className="tz-sheet tz-sheet-flat">
        <thead>
          <tr>
            <th className="tz-fix tz-fix-1 blk-metal">Головной контрагент</th>
            <th className="blk-metal">Менеджер</th>
            <th className="blk-metal">Тип работы</th>
            <th className="blk-metal">% типа работы</th>
            <th className="blk-lts">{labels.plan || "План отгрузок последний квартал"}</th>
            <th className="blk-lts">{labels.shipment_fact || "Факт отгрузок последний"}</th>
            <th className="blk-lts">{labels.shipment_percent || "% выполнения"}</th>
            <th className="blk-lts">{labels.shipment_prev || "Факт отгрузок пред. кв."}</th>
            <th className="blk-lts">{labels.shipment_prev2 || "Факт отгрузок предпред. кв."}</th>
            <th className="blk-lts">{labels.shipment_dynamics || "Динамика отгрузок"}</th>
            <th className="blk-wear">{labels.sales || "Продажи последний кв."}</th>
            <th className="blk-wear">{labels.sales_prev || "Продажи пред. кв."}</th>
            <th className="blk-wear">{labels.sales_prev2 || "Продажи предпред. кв."}</th>
            <th className="blk-wear">{labels.sales_dynamics || "Динамика продаж"}</th>
            <th>Комментарий</th>
          </tr>
        </thead>
        <tbody>
          {!filtered.length && (
            <tr>
              <td colSpan={15}>
                Нет акционных клиентов за {year} Q{quarter}
              </td>
            </tr>
          )}
          {filtered.map((client) => (
            <tr key={client.counterparty_id}>
              <td className="tz-name tz-fix tz-fix-1">{client.counterparty}</td>
              <td>{client.manager_name || "—"}</td>
              <td>{workTypeLabel(client.work_type_label || client.work_type)}</td>
              <td className="num">{formatWorkTypePercent(client.work_type_percent)}</td>
              <td className="num">{qty(client.plan)}</td>
              <td className="num">{qty(client.shipment_fact)}</td>
              <td className="num">{pct(client.shipment_percent)}</td>
              <td className="num">{qty(client.shipment_prev_quarter)}</td>
              <td className="num">{qty(client.shipment_prev2_quarter)}</td>
              <td className={`num ${dynPctClass(client.shipment_dynamics_percent)}`}>
                {pct(client.shipment_dynamics_percent)}
              </td>
              <td className="num">{qty(client.sales_total)}</td>
              <td className="num">{qty(client.sales_prev_quarter)}</td>
              <td className="num">{qty(client.sales_prev2_quarter)}</td>
              <td className={`num ${dynPctClass(client.dynamics_percent)}`}>{pct(client.dynamics_percent)}</td>
              <CommentCell
                comment={client.comment}
                draft={drafts[client.counterparty_id] ?? ""}
                saving={saving === client.counterparty_id}
                canEdit={Boolean(onSaveComment)}
                onDraftChange={(value) => setDrafts((prev) => ({ ...prev, [client.counterparty_id]: value }))}
                onSave={() => {
                  void save(client.counterparty_id);
                }}
                onShowHistory={onShowHistory ? () => onShowHistory(client.counterparty_id) : undefined}
              />
            </tr>
          ))}
        </tbody>
      </table>
      </TzScrollPane>
    </div>
  );
}
