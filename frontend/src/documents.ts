export const DOC_TYPE_LABEL: Record<string, string> = {
  realization: "Реализация",
  return: "Возврат",
  order: "Заказ",
  production: "Поступление продукции из производства",
  goods: "Поступление товаров и услуг",
};

export type DocumentJournalTab = {
  id: string;
  label: string;
  endpoint: string;
  docType?: "production" | "goods";
};

export function documentJournalListUrl(
  tab: Pick<DocumentJournalTab, "endpoint" | "docType">,
  params: URLSearchParams,
): string {
  if (tab.docType) {
    params.set("doc_type", tab.docType);
  }
  return `/api/v1/documents/${tab.endpoint}?${params}`;
}

export function documentJournalDetailUrl(
  tab: Pick<DocumentJournalTab, "endpoint">,
  sourceId: string,
  onecRef: string,
): string {
  return `/api/v1/documents/${tab.endpoint}/${sourceId}/${onecRef}`;
}

export function docTypeLabel(type?: string | null): string {
  if (!type) return "";
  return DOC_TYPE_LABEL[type] || type;
}

export function linesQuantity(lines: { quantity?: number | null }[] | undefined): number {
  return (lines || []).reduce((sum, line) => sum + Number(line.quantity || 0), 0);
}

export function documentTotalQuantity(
  totalQuantity?: number | null,
  lines?: { quantity?: number | null }[],
): number {
  const fromLines = linesQuantity(lines);
  return fromLines || Number(totalQuantity || 0);
}

export function documentListNumber(doc: { doc_number?: string | null }): string {
  const number = (doc.doc_number || "").trim();
  return number || "—";
}
