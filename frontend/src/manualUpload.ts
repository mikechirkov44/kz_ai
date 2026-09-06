export type ManualLine = {
  key: string;
  article: string;
  shop: string;
  quantity: string;
  price: string;
};

export type ManualSubmitRow = {
  counterparty: string;
  article: string;
  shop?: string | null;
  quantity: number;
  price?: number | null;
};

export function newManualLine(): ManualLine {
  const key =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `row-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return { key, article: "", shop: "", quantity: "1", price: "" };
}

export function parsePositiveInt(value: string): number | null {
  const n = Number(String(value).replace(",", ".").replace(/\s/g, ""));
  if (!Number.isInteger(n) || n <= 0) return null;
  return n;
}

export function parseOptionalPrice(value: string): number | null | undefined {
  const text = value.trim().replace(/\u00a0/g, "").replace(/\s/g, "").replace(",", ".");
  if (!text) return undefined;
  const n = Number(text);
  if (!Number.isFinite(n) || n < 0) return null;
  return n;
}

export function needsStockDate(uploadType: string): boolean {
  return uploadType === "stocks" || uploadType === "both";
}

export function needsSalePrice(uploadType: string): boolean {
  return uploadType === "sales" || uploadType === "both";
}

export function buildManualRows(
  counterpartyName: string,
  lines: ManualLine[],
): { rows: ManualSubmitRow[]; error: string } {
  if (!counterpartyName.trim()) {
    return { rows: [], error: "Выберите контрагента" };
  }
  if (!lines.length) {
    return { rows: [], error: "Добавьте хотя бы одну строку" };
  }
  const rows: ManualSubmitRow[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.article.trim()) {
      return { rows: [], error: `Строка ${i + 1}: укажите артикул` };
    }
    const quantity = parsePositiveInt(line.quantity);
    if (quantity == null) {
      return { rows: [], error: `Строка ${i + 1}: количество должно быть целым числом больше 0` };
    }
    const price = parseOptionalPrice(line.price);
    if (price === null) {
      return { rows: [], error: `Строка ${i + 1}: некорректная цена` };
    }
    rows.push({
      counterparty: counterpartyName.trim(),
      article: line.article.trim(),
      shop: line.shop.trim() || null,
      quantity,
      price,
    });
  }
  return { rows, error: "" };
}
