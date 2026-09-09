import { useEffect, useMemo, useRef, useState } from "react";
import { Counterparty, listCounterparties } from "../api";
import { sourceLabel, useODataSources } from "../odataSources";
import Select from "./Select";

type BaseProps = {
  onCreateName?: (name: string) => void;
  promoOnly?: boolean;
  sourceId?: string;
  allowEmpty?: boolean;
  allowCreate?: boolean;
  compact?: boolean;
  emptyLabel?: string;
};

type SingleProps = BaseProps & {
  multiple?: false;
  value: string;
  onChange: (id: string) => void;
  onSelect?: (counterparty: Counterparty | null) => void;
};

type MultiProps = BaseProps & {
  multiple: true;
  value: string[];
  onChange: (ids: string[]) => void;
};

type Props = SingleProps | MultiProps;

function optionLabel(c: Counterparty, sources: { source_id: string; label: string }[]): string {
  const base = sourceLabel(c.source_id, sources);
  return `${c.name}${c.is_promo ? " ★" : ""} [${base}]`;
}

function isMulti(props: Props): props is MultiProps {
  return props.multiple === true;
}

export default function CounterpartySelect(props: Props) {
  const {
    onCreateName,
    promoOnly = false,
    sourceId,
    allowEmpty = false,
    allowCreate = false,
    compact = false,
    emptyLabel = "— выберите —",
  } = props;
  const [rows, setRows] = useState<Counterparty[]>([]);
  const [q, setQ] = useState("");
  const picked = useRef<Map<string, Counterparty>>(new Map());
  const { sources } = useODataSources();
  const selectedIds = isMulti(props) ? props.value : props.value ? [props.value] : [];

  useEffect(() => {
    for (const row of rows) {
      if (selectedIds.includes(row.id)) picked.current.set(row.id, row);
    }
  }, [rows, selectedIds]);

  function emit(ids: string[], list: Counterparty[] = rows) {
    if (isMulti(props)) {
      props.onChange(ids);
      return;
    }
    const id = ids[0] || "";
    const found = list.find((c) => c.id === id) || picked.current.get(id) || null;
    if (found) {
      props.onChange(id);
      props.onSelect?.(found);
      return;
    }
    if (allowCreate && id) {
      props.onChange("");
      onCreateName?.(id);
      props.onSelect?.(null);
      return;
    }
    props.onChange(id);
    props.onSelect?.(null);
  }

  useEffect(() => {
    const t = setTimeout(() => {
      listCounterparties({ promo_only: promoOnly, source_id: sourceId, q: q || undefined })
        .then((data) => {
          setRows(data);
          if (!allowEmpty && !isMulti(props) && !props.value && !q && data[0]) emit([data[0].id], data);
        })
        .catch(() => setRows([]));
    }, 200);
    return () => clearTimeout(t);
  }, [promoOnly, sourceId, q]); // eslint-disable-line react-hooks/exhaustive-deps

  const options = useMemo(() => {
    const ids = new Set(rows.map((c) => c.id));
    const extra = [...picked.current.values()].filter((c) => selectedIds.includes(c.id) && !ids.has(c.id));
    return [
      ...(allowEmpty ? [{ value: "", label: emptyLabel }] : []),
      ...[...extra, ...rows].map((c) => ({ value: c.id, label: optionLabel(c, sources) })),
    ];
  }, [allowEmpty, emptyLabel, rows, selectedIds, sources]);

  const select = isMulti(props) ? (
    <Select
      multiple
      value={selectedIds}
      onChange={(next) => emit(next)}
      options={options}
      placeholder={rows.length || selectedIds.length ? "Выберите" : "Нет данных"}
      search={q}
      onSearch={setQ}
      searchPlaceholder="Найти контрагента"
      allowCreate={allowCreate}
    />
  ) : (
    <Select
      value={props.value}
      onChange={(next) => emit(next ? [next] : [])}
      options={options}
      placeholder={rows.length || selectedIds.length ? "Выберите" : "Нет данных"}
      search={q}
      onSearch={setQ}
      searchPlaceholder="Найти контрагента"
      allowCreate={allowCreate}
    />
  );

  if (compact) {
    return (
      <label className="field">
        <span>Контрагент</span>
        {select}
      </label>
    );
  }

  return (
    <label className="field">
      <span>Контрагент</span>
      {select}
    </label>
  );
}
