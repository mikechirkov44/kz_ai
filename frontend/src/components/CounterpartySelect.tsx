import { useEffect, useMemo, useRef, useState } from "react";
import { Counterparty, listCounterparties } from "../api";
import { sourceLabel, useODataSources } from "../odataSources";
import Select from "./Select";

type Props = {
  value: string;
  onChange: (id: string) => void;
  onSelect?: (counterparty: Counterparty | null) => void;
  onCreateName?: (name: string) => void;
  promoOnly?: boolean;
  sourceId?: string;
  allowEmpty?: boolean;
  allowCreate?: boolean;
  compact?: boolean;
  emptyLabel?: string;
};

function optionLabel(c: Counterparty, sources: { source_id: string; label: string }[]): string {
  const base = sourceLabel(c.source_id, sources);
  return `${c.name}${c.is_promo ? " ★" : ""} [${base}]`;
}

export default function CounterpartySelect({
  value,
  onChange,
  onSelect,
  onCreateName,
  promoOnly = false,
  sourceId,
  allowEmpty = false,
  allowCreate = false,
  compact = false,
  emptyLabel = "— выберите —",
}: Props) {
  const [rows, setRows] = useState<Counterparty[]>([]);
  const [q, setQ] = useState("");
  const picked = useRef<Counterparty | null>(null);
  const { sources } = useODataSources();

  useEffect(() => {
    const found = rows.find((c) => c.id === value);
    if (found) picked.current = found;
  }, [rows, value]);

  function pick(id: string, list: Counterparty[] = rows) {
    const found = list.find((c) => c.id === id) || (picked.current?.id === id ? picked.current : null);
    if (found) {
      onChange(id);
      onSelect?.(found);
      return;
    }
    if (allowCreate && id) {
      onChange("");
      onCreateName?.(id);
      onSelect?.(null);
      return;
    }
    onChange(id);
    onSelect?.(null);
  }

  useEffect(() => {
    const t = setTimeout(() => {
      listCounterparties({ promo_only: promoOnly, source_id: sourceId, q: q || undefined })
        .then((data) => {
          setRows(data);
          if (!allowEmpty && !value && !q && data[0]) pick(data[0].id, data);
        })
        .catch(() => setRows([]));
    }, 200);
    return () => clearTimeout(t);
  }, [promoOnly, sourceId, q]); // eslint-disable-line react-hooks/exhaustive-deps

  const options = useMemo(() => {
    const ids = new Set(rows.map((c) => c.id));
    const extra = picked.current && value && !ids.has(value) ? [picked.current] : [];
    return [
      ...(allowEmpty ? [{ value: "", label: emptyLabel }] : []),
      ...[...extra, ...rows].map((c) => ({ value: c.id, label: optionLabel(c, sources) })),
    ];
  }, [allowEmpty, emptyLabel, rows, value, sources]);

  if (compact) {
    return (
      <label className="field">
        <span>Контрагент</span>
        <Select
          value={value}
          onChange={pick}
          options={options}
          placeholder={rows.length || value ? "Выберите" : "Нет данных"}
          search={q}
          onSearch={setQ}
          searchPlaceholder="Найти контрагента"
          allowCreate={allowCreate}
        />
      </label>
    );
  }

  return (
    <label className="field">
      <span>Контрагент</span>
      <Select
        value={value}
        onChange={pick}
        options={options}
        placeholder={rows.length || value ? "Выберите" : "Нет данных"}
        search={q}
        onSearch={setQ}
        searchPlaceholder="Найти контрагента"
        allowCreate={allowCreate}
      />
    </label>
  );
}
