import { useEffect, useMemo, useRef, useState } from "react";
import { listNomenclature, NomenclatureItem } from "../api";
import Select from "./Select";

type Props = {
  value: string;
  onChange: (article: string) => void;
};

function optionValue(item: NomenclatureItem): string {
  return (item.article || item.barcode || "").trim();
}

function optionLabel(item: NomenclatureItem): string {
  const article = optionValue(item);
  return item.name ? `${article} — ${item.name}` : article;
}

export default function ArticleSelect({ value, onChange }: Props) {
  const [rows, setRows] = useState<NomenclatureItem[]>([]);
  const [q, setQ] = useState("");
  const picked = useRef<NomenclatureItem | null>(null);

  useEffect(() => {
    const found = rows.find((item) => optionValue(item) === value);
    if (found) picked.current = found;
  }, [rows, value]);

  useEffect(() => {
    const t = setTimeout(() => {
      listNomenclature({ q: q || undefined })
        .then(setRows)
        .catch(() => setRows([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  const options = useMemo(() => {
    const values = new Set(rows.map(optionValue).filter(Boolean));
    const extra = picked.current && value && !values.has(value) ? [picked.current] : [];
    return [...extra, ...rows]
      .filter((item) => optionValue(item))
      .map((item) => ({ value: optionValue(item), label: optionLabel(item) }));
  }, [rows, value]);

  return (
    <Select
      value={value}
      onChange={onChange}
      options={options}
      placeholder="Артикул"
      search={q}
      onSearch={setQ}
      searchPlaceholder="Артикул или название"
      allowCreate
    />
  );
}
