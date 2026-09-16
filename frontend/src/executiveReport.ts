import {
  recActionLabel,
  priceArticleRows,
  type RecAction,
  type RecActionCounts,
  type Recommendation,
} from "./recommendations";

export const PLAN_BEHIND_PERCENT = 50;
export const EXEC_PLAYBOOK_LIMIT = 5;
export const EXEC_FOCUS_LIMIT = 5;
export const EXEC_TOP_LIMIT = 3;
export const EXEC_WEAR_LIMIT = 5;

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

export function isExitLts(details: Record<string, unknown> | undefined): boolean {
  return detailText(details, "lts").toLowerCase().includes("вывод");
}

export function itemPlanPercent(item: Recommendation): number | null {
  return detailNumber(item.details, "plan_percent");
}

function clientName(item: Recommendation): string {
  return item.counterparty || "Без клиента";
}

function itemScore(item: Recommendation): number {
  return item.score || 0;
}

function avg(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, n) => sum + n, 0) / values.length;
}

function pctLabel(value: number): string {
  return `${value.toFixed(1)}%`;
}

export type ExecLine = {
  counterparty: string;
  title: string;
  metric: string;
  tag?: string;
  clientAvg?: number | null;
  shipmentAvg?: number | null;
  gapPercent?: number | null;
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
  planPercent: number | null;
  behind: boolean;
  score: number;
};

export type ExecPlayStep = {
  action: RecAction;
  actionLabel: string;
  counterparty: string;
  title: string;
  why: string;
};

export type ExecWear = {
  wear: string;
  count: number;
};

export type ExecReport = {
  total: number;
  clients: number;
  behindPlan: number;
  planKnown: number;
  mixCount: number;
  exitLts: number;
  severity: { high: number; medium: number; info: number };
  actions: RecActionCounts;
  blocks: ExecActionBlock[];
  focus: ExecFocus[];
  playbook: ExecPlayStep[];
  wear: ExecWear[];
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

function sortByPriority(items: Recommendation[]): Recommendation[] {
  return [...items].sort((a, b) => {
    const score = itemScore(b) - itemScore(a);
    if (score) return score;
    const qty = (detailNumber(b.details, "suggest_qty") || 0) - (detailNumber(a.details, "suggest_qty") || 0);
    if (qty) return qty;
    const gap = (detailNumber(b.details, "gap_percent") || 0) - (detailNumber(a.details, "gap_percent") || 0);
    return gap;
  });
}

export function playbookWhy(item: Recommendation): string {
  const bits: string[] = [];
  const plan = itemPlanPercent(item);
  if (plan != null) bits.push(`план ${pctLabel(plan)}`);
  const months = detailNumber(item.details, "months_without_sales");
  if (months != null && months > 0) bits.push(`${Math.round(months)} мес. без продаж`);
  const gap = detailNumber(item.details, "gap_percent");
  if (gap != null) bits.push(`разрыв ${pctLabel(gap)}`);
  const dest = detailText(item.details, "to_counterparty");
  if (dest) bits.push(`→ ${dest}`);
  if (item.type === "mix") bits.push("перекос ассортимента");
  if (isExitLts(item.details)) bits.push("ЖЦТ Вывод");
  const sku = priceArticleRows(item.details)[0]?.article;
  if (sku) bits.push(sku);
  return bits.join(" · ");
}

export function buildPlaybook(items: Recommendation[], limit = EXEC_PLAYBOOK_LIMIT): ExecPlayStep[] {
  const seen = new Set<string>();
  const steps: ExecPlayStep[] = [];
  for (const item of sortByPriority(items)) {
    const action = item.action;
    if (action !== "return" && action !== "restock" && action !== "transfer" && action !== "reprice") continue;
    const key = `${clientName(item)}:${action}`;
    if (seen.has(key)) continue;
    seen.add(key);
    steps.push({
      action,
      actionLabel: recActionLabel(action),
      counterparty: clientName(item),
      title: item.title || item.message,
      why: playbookWhy(item),
    });
    if (steps.length >= limit) break;
  }
  return steps;
}

function clientPlan(items: Recommendation[]): number | null {
  let shown: number | null = null;
  let behind: number | null = null;
  for (const item of items) {
    const pct = itemPlanPercent(item);
    if (pct == null) continue;
    if (shown == null) shown = pct;
    if (pct < PLAN_BEHIND_PERCENT && (behind == null || pct < behind)) behind = pct;
  }
  return behind ?? shown;
}

function topLine(item: Recommendation): ExecLine {
  const dest = detailText(item.details, "to_counterparty");
  const suggest = detailNumber(item.details, "suggest_qty");
  const gap = detailNumber(item.details, "gap_percent");
  const plan = itemPlanPercent(item);
  const metricBits: string[] = [];
  if (suggest != null && item.action !== "reprice") metricBits.push(`${Math.round(suggest)} шт.`);
  if (gap != null) metricBits.push(`разрыв ${pctLabel(gap)}`);
  if (plan != null && plan < PLAN_BEHIND_PERCENT) metricBits.push(`план ${pctLabel(plan)}`);
  const wear = detailText(item.details, "wear_type");
  const title = item.action === "reprice" && wear ? wear : item.title || item.message;
  return {
    counterparty: dest ? `${clientName(item)} → ${dest}` : clientName(item),
    title,
    metric: metricBits.join(" · "),
    tag: item.type === "mix" ? "Перекос" : isExitLts(item.details) ? "Вывод" : undefined,
  };
}

function priceBlock(items: Recommendation[]): ExecActionBlock {
  const gaps = items
    .map((item) => detailNumber(item.details, "gap_percent"))
    .filter((n): n is number => n != null);
  const facts: { label: string; value: string }[] = [{ label: "Клиентов", value: String(uniqueClients(items)) }];
  const mean = avg(gaps);
  const max = gaps.length ? Math.max(...gaps) : null;
  if (mean != null) facts.push({ label: "Средний разрыв", value: pctLabel(mean) });
  if (max != null) facts.push({ label: "Макс. разрыв", value: pctLabel(max) });
  const skuCount = new Set(
    items.flatMap((item) => priceArticleRows(item.details).map((row) => row.article)),
  ).size;
  if (skuCount) facts.push({ label: "Артикулов", value: String(skuCount) });
  const top: ExecLine[] = [];
  for (const item of sortByPriority(items)) {
    const arts = priceArticleRows(item.details);
    if (arts.length) {
      for (const art of arts) {
        top.push({
          counterparty: clientName(item),
          title: art.article,
          metric: art.gapPercent != null ? `разрыв ${pctLabel(art.gapPercent)}` : "",
          clientAvg: art.clientAvgPrice,
          shipmentAvg: art.shipmentAvgPrice,
          gapPercent: art.gapPercent,
        });
      }
    } else {
      top.push(topLine(item));
    }
  }
  return {
    action: "reprice",
    label: recActionLabel("reprice"),
    count: items.length,
    clients: uniqueClients(items),
    empty: EMPTY.reprice,
    facts,
    top: top.slice(0, 5),
  };
}

function qtyBlock(
  action: RecAction,
  items: Recommendation[],
  extra?: (rows: Recommendation[]) => { label: string; value: string }[],
): ExecActionBlock {
  const qty = qtySum(items);
  const facts: { label: string; value: string }[] = [
    { label: "Клиентов", value: String(uniqueClients(items)) },
    { label: "Штук", value: String(Math.round(qty)) },
  ];
  if (extra) facts.push(...extra(items));
  return {
    action,
    label: recActionLabel(action),
    count: items.length,
    clients: uniqueClients(items),
    empty: EMPTY[action],
    facts,
    top: sortByPriority(items).slice(0, EXEC_TOP_LIMIT).map(topLine),
  };
}

function buildFocus(items: Recommendation[]): ExecFocus[] {
  const groups = new Map<string, Recommendation[]>();
  for (const item of items) {
    const name = clientName(item);
    const list = groups.get(name) || [];
    list.push(item);
    groups.set(name, list);
  }
  return [...groups.entries()]
    .map(([counterparty, rows]) => {
      const top = sortByPriority(rows)[0];
      const planPercent = clientPlan(rows);
      const actions = [...new Set(rows.map((row) => (row.action ? recActionLabel(row.action) : "")).filter(Boolean))];
      return {
        counterparty,
        signals: rows.length,
        actions,
        title: top?.title || top?.message || "",
        planPercent,
        behind: planPercent != null && planPercent < PLAN_BEHIND_PERCENT,
        score: top ? itemScore(top) : 0,
      };
    })
    .sort((a, b) => {
      if (a.behind !== b.behind) return a.behind ? -1 : 1;
      if (a.behind && b.behind) {
        const plan = (a.planPercent ?? 100) - (b.planPercent ?? 100);
        if (plan) return plan;
      }
      return b.score - a.score || b.signals - a.signals;
    })
    .slice(0, EXEC_FOCUS_LIMIT);
}

function buildWear(items: Recommendation[]): ExecWear[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const wear = detailText(item.details, "wear_type");
    if (!wear) continue;
    counts.set(wear, (counts.get(wear) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([wear, count]) => ({ wear, count }))
    .sort((a, b) => b.count - a.count || a.wear.localeCompare(b.wear, "ru"))
    .slice(0, EXEC_WEAR_LIMIT);
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
  const mixCount = items.filter((item) => item.type === "mix").length;
  const exitLts = items.filter((item) => isExitLts(item.details)).length;
  const planByClient = new Map<string, number>();
  for (const item of items) {
    const name = clientName(item);
    const pct = itemPlanPercent(item);
    if (pct == null) continue;
    const prev = planByClient.get(name);
    if (prev == null || pct < prev) planByClient.set(name, pct);
  }
  const behindPlan = [...planByClient.values()].filter((pct) => pct < PLAN_BEHIND_PERCENT).length;

  return {
    total: items.length,
    clients: uniqueClients(items),
    behindPlan,
    planKnown: planByClient.size,
    mixCount,
    exitLts,
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
      qtyBlock("return", returns, (rows) => {
        const extra: { label: string; value: string }[] = [];
        const mean = avg(months);
        if (mean != null) extra.push({ label: "Средний простой", value: `${mean.toFixed(1)} мес.` });
        const mix = rows.filter((item) => item.type === "mix").length;
        if (mix) extra.push({ label: "Перекос", value: String(mix) });
        const exit = rows.filter((item) => isExitLts(item.details)).length;
        if (exit) extra.push({ label: "ЖЦТ Вывод", value: String(exit) });
        return extra;
      }),
      qtyBlock("restock", restocks),
      qtyBlock("transfer", transfers, (rows) => {
        const dests = new Set(rows.map((item) => detailText(item.details, "to_counterparty")).filter(Boolean));
        return dests.size ? [{ label: "Куда везти", value: String(dests.size) }] : [];
      }),
      priceBlock(prices),
    ],
    focus: buildFocus(items),
    playbook: buildPlaybook(items),
    wear: buildWear(items),
  };
}
