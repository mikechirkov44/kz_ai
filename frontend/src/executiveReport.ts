import {
  recActionLabel,
  type RecAction,
  type RecActionCounts,
  type Recommendation,
} from "./recommendations";

export function detailNumber(details: Record<string, unknown> | undefined, key: string): number | null {
  const raw = details?.[key];
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw !== "string") return null;
  const n = Number(raw.replace(/\s|\u00a0|\u202f/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

export function detailText(details: Record<string, unknown> | undefined, key: string): string {
  const raw = details?.[key];
  return typeof raw === "string" && raw.trim() && raw !== "—" ? raw.trim() : "";
}

function clientName(item: Recommendation): string {
  return item.counterparty || "Без клиента";
}

function avg(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, n) => sum + n, 0) / values.length;
}

export type ExecLine = {
  counterparty: string;
  title: string;
  metric: string;
};

export type ExecActionBlock = {
  action: RecAction;
  label: string;
  count: number;
  clients: number;
  empty: string;
  facts: { label: string; value: string }[];
  top: ExecLine[];
};

export type ExecFocus = {
  counterparty: string;
  signals: number;
  actions: string[];
  title: string;
};

export type ExecReport = {
  total: number;
  clients: number;
  severity: { high: number; medium: number; info: number };
  actions: RecActionCounts;
  blocks: ExecActionBlock[];
  focus: ExecFocus[];
};

const EMPTY: Record<RecAction, string> = {
  return: "Сигналов на возврат нет.",
  restock: "Подсортировка не требуется.",
  transfer: "Перекладывать нечего.",
  reprice: "Разрывов по цене отгрузки нет.",
};

function uniqueClients(items: Recommendation[]): number {
  return new Set(items.map(clientName)).size;
}

function qtySum(items: Recommendation[]): number {
  return items.reduce((sum, item) => sum + (detailNumber(item.details, "suggest_qty") || 0), 0);
}

function priceBlock(items: Recommendation[]): ExecActionBlock {
  const gaps = items
    .map((item) => detailNumber(item.details, "gap_percent"))
    .filter((n): n is number => n != null);
  const top = [...items]
    .sort((a, b) => (detailNumber(b.details, "gap_percent") || 0) - (detailNumber(a.details, "gap_percent") || 0))
    .slice(0, 3)
    .map((item) => {
      const gap = detailNumber(item.details, "gap_percent");
      const wear = detailText(item.details, "wear_type");
      return {
        counterparty: clientName(item),
        title: wear ? `${wear}` : item.title || item.message,
        metric: gap != null ? `разрыв ${gap.toFixed(1)}%` : "",
      };
    });
  const facts: { label: string; value: string }[] = [{ label: "Клиентов", value: String(uniqueClients(items)) }];
  const mean = avg(gaps);
  const max = gaps.length ? Math.max(...gaps) : null;
  if (mean != null) facts.push({ label: "Средний разрыв", value: `${mean.toFixed(1)}%` });
  if (max != null) facts.push({ label: "Макс. разрыв", value: `${max.toFixed(1)}%` });
  return {
    action: "reprice",
    label: recActionLabel("reprice"),
    count: items.length,
    clients: uniqueClients(items),
    empty: EMPTY.reprice,
    facts,
    top,
  };
}

function qtyBlock(action: RecAction, items: Recommendation[], extra?: (rows: Recommendation[]) => { label: string; value: string }[]): ExecActionBlock {
  const qty = qtySum(items);
  const facts: { label: string; value: string }[] = [
    { label: "Клиентов", value: String(uniqueClients(items)) },
    { label: "Штук", value: String(Math.round(qty)) },
  ];
  if (extra) facts.push(...extra(items));
  const top = [...items]
    .sort((a, b) => (detailNumber(b.details, "suggest_qty") || 0) - (detailNumber(a.details, "suggest_qty") || 0))
    .slice(0, 3)
    .map((item) => {
      const suggest = detailNumber(item.details, "suggest_qty");
      const dest = detailText(item.details, "to_counterparty");
      return {
        counterparty: dest ? `${clientName(item)} → ${dest}` : clientName(item),
        title: item.title || item.message,
        metric: suggest != null ? `${Math.round(suggest)} шт.` : "",
      };
    });
  return {
    action,
    label: recActionLabel(action),
    count: items.length,
    clients: uniqueClients(items),
    empty: EMPTY[action],
    facts,
    top,
  };
}

export function buildExecutiveReport(items: Recommendation[]): ExecReport {
  const byAction = (action: RecAction) => items.filter((item) => item.action === action);
  const returns = byAction("return");
  const restocks = byAction("restock");
  const transfers = byAction("transfer");
  const prices = byAction("reprice");
  const months = returns
    .map((item) => detailNumber(item.details, "months_without_sales"))
    .filter((n): n is number => n != null && n > 0);

  const focusMap = new Map<string, { signals: number; actions: Set<string>; title: string; score: number }>();
  for (const item of items) {
    const name = clientName(item);
    const prev = focusMap.get(name) || { signals: 0, actions: new Set<string>(), title: item.title || item.message, score: 0 };
    prev.signals += 1;
    if (item.action) prev.actions.add(recActionLabel(item.action));
    if ((item.score || 0) > prev.score) {
      prev.score = item.score || 0;
      prev.title = item.title || item.message;
    }
    focusMap.set(name, prev);
  }
  const focus = [...focusMap.entries()]
    .map(([counterparty, row]) => ({
      counterparty,
      signals: row.signals,
      actions: [...row.actions],
      title: row.title,
    }))
    .sort((a, b) => b.actions.length - a.actions.length || b.signals - a.signals)
    .slice(0, 5);

  return {
    total: items.length,
    clients: uniqueClients(items),
    severity: {
      high: items.filter((item) => item.severity === "high").length,
      medium: items.filter((item) => item.severity === "medium").length,
      info: items.filter((item) => item.severity === "info" || item.severity === "low").length,
    },
    actions: {
      return: returns.length,
      restock: restocks.length,
      transfer: transfers.length,
      reprice: prices.length,
    },
    blocks: [
      qtyBlock("return", returns, () => {
        const mean = avg(months);
        return mean != null ? [{ label: "Средний простой", value: `${mean.toFixed(1)} мес.` }] : [];
      }),
      qtyBlock("restock", restocks),
      qtyBlock("transfer", transfers),
      priceBlock(prices),
    ],
    focus,
  };
}
