import { useEffect, useMemo, useRef, useState } from "react";
import { Counterparty, listCounterparties } from "../api";
import Select from "./Select";

type Props = {
  value: string;
  onChange: (id: string) => void;
  promoOnly?: boolean;
  sourceId?: string;
  allowEmpty?: boolean;
  compact?: boolean;
  emptyLabel?: string;
};

function optionLabel(c: Counterparty): string {
  return `${c.name}${c.is_promo ? " ★" : ""} [${c.source_id}]`;
}

export default function CounterpartySelect({
  value,
  onChange,
  promoOnly = false,
  sourceId,
  allowEmpty = false,
  compact = false,
  emptyLabel = "— выберите —",
}: Props) {
  const [rows, setRows] = useState<Counterparty[]>([]);
  const [q, setQ] = useState("");
  const picked = useRef<Counterparty | null>(null);

  useEffect(() => {
    const found = rows.find((c) => c.id === value);
    if (found) picked.current = found;
  }, [rows, value]);

  useEffect(() => {
    const t = setTimeout(() => {
      listCounterparties({ promo_only: promoOnly, source_id: sourceId, q: q || undefined })
        .then((data) => {
          setRows(data);
          if (!allowEmpty && !value && !q && data[0]) onChange(data[0].id);
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
      ...[...extra, ...rows].map((c) => ({ value: c.id, label: optionLabel(c) })),
    ];
  }, [allowEmpty, emptyLabel, rows, value]);

  if (compact) {
    return (
      <label className="field">
        <span>Контрагент</span>
        <Select
          value={value}
          onChange={onChange}
          options={options}
          placeholder={rows.length || value ? "Выберите" : "Нет данных"}
          search={q}
          onSearch={setQ}
          searchPlaceholder="Найти контрагента"
        />
      </label>
    );
  }

  return (
    <div className="grid-2" style={{ gap: 10 }}>
      <label className="field">
        <span>Поиск</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Имя контрагента" />
      </label>
      <label className="field">
        <span>Контрагент</span>
        <Select
          value={value}
          onChange={onChange}
          options={options}
          placeholder={rows.length || value ? "Выберите" : "Нет данных"}
        />
      </label>
    </div>
  );
}
