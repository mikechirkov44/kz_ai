import { visibleDetailRows, type DetailRow } from "./nomenclatureDetails";

export type CounterpartyCard = {
  name?: string | null;
  full_name?: string | null;
  code?: string | null;
  parent_name?: string | null;
  legal_status?: string | null;
  is_buyer?: boolean | null;
  is_supplier?: boolean | null;
  iin?: string | null;
  identity_document?: string | null;
  rnn?: string | null;
  sik?: string | null;
  okpo?: string | null;
  kbe?: string | null;
  director_name?: string | null;
  work_schedule?: string | null;
  comment?: string | null;
  extra_properties?: Record<string, string> | null;
};

export function counterpartyMainRows(item: CounterpartyCard): DetailRow[] {
  return [
    { label: "Наименование", value: item.name, always: true },
    { label: "Полное наименование", value: item.full_name },
    { label: "Код", value: item.code },
    { label: "Группа", value: item.parent_name },
    { label: "Правовой статус", value: item.legal_status },
    { label: "Покупатель", value: item.is_buyer ? true : null },
    { label: "Поставщик", value: item.is_supplier ? true : null },
  ];
}

export function counterpartyRequisiteRows(item: CounterpartyCard): DetailRow[] {
  return [
    { label: "БИН / ИИН", value: item.iin },
    { label: "Документ", value: item.identity_document },
    { label: "РНН", value: item.rnn },
    { label: "СИК", value: item.sik },
    { label: "ОКПО", value: item.okpo },
    { label: "КБЕ", value: item.kbe },
  ];
}

export function counterpartyOtherRows(item: CounterpartyCard): DetailRow[] {
  return [
    { label: "Руководитель", value: item.director_name },
    { label: "Расписание работы", value: item.work_schedule },
    { label: "Комментарий", value: item.comment },
  ];
}

export function extraPropertyRows(
  props?: Record<string, string> | null,
): { label: string; text: string }[] {
  const rows: DetailRow[] = Object.entries(props || {})
    .filter(([label, value]) => label !== "Участвует в акции" && String(value || "").trim())
    .sort(([left], [right]) => left.localeCompare(right, "ru"))
    .map(([label, value]) => ({ label, value }));
  return visibleDetailRows(rows);
}
