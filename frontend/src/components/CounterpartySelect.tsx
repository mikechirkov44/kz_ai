import { useEffect, useState } from "react";
import { Counterparty, listCounterparties } from "../api";
import Select from "./Select";

type Props = {
  value: string;
  onChange: (id: string) => void;
  promoOnly?: boolean;
  sourceId?: string;
  allowEmpty?: boolean;
};

export default function CounterpartySelect({
  value,
  onChange,
  promoOnly = false,
  sourceId,
  allowEmpty = false,
}: Props) {
  const [rows, setRows] = useState<Counterparty[]>([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      listCounterparties({ promo_only: promoOnly, source_id: sourceId, q: q || undefined })
        .then((data) => {
          setRows(data);
          if (!allowEmpty && !value && data[0]) onChange(data[0].id);
        })
        .catch(() => setRows([]));
    }, 200);
    return () => clearTimeout(t);
  }, [promoOnly, sourceId, q]); // eslint-disable-line react-hooks/exhaustive-deps

  const options = [
    ...(allowEmpty ? [{ value: "", label: "— выберите —" }] : []),
    ...rows.map((c) => ({
      value: c.id,
      label: `${c.name}${c.is_promo ? " ★" : ""} [${c.source_id}]`,
    })),
  ];

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
          placeholder={rows.length ? "Выберите" : "Нет данных"}
        />
      </label>
    </div>
  );
}
