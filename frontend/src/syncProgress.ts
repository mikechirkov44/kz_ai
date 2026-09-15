export const SYNC_STATUS_LABELS: Record<string, string> = {
  idle: "ожидание",
  queued: "в очереди",
  running: "выполняется",
  success: "готово",
  failed: "ошибка",
};

export function syncStatusLabel(status: string): string {
  return SYNC_STATUS_LABELS[status] || status;
}

export function syncRowKey(sourceId: string, entity: string): string {
  return `${sourceId}:${entity}`;
}

export const SYNC_DOCUMENT_ENTITIES = new Set([
  "realization",
  "return_doc",
  "client_order",
  "production_receipt",
]);

export function syncCountUnit(entity: string): "документов" | "записей" {
  return SYNC_DOCUMENT_ENTITIES.has(entity) ? "документов" : "записей";
}

export function formatSyncCount(value: number): string {
  return value.toLocaleString("ru-RU");
}

export function syncProgressPercent(done: number, expected: number, status: string): number | null {
  if (status === "success") return 100;
  if (expected <= 0) return null;
  const pct = Math.floor((Math.max(0, done) * 100) / expected);
  if ((status === "running" || status === "queued") && pct >= 100) return 99;
  return Math.min(100, pct);
}

export function syncIsBusy(status: string): boolean {
  return status === "running" || status === "queued";
}

export function syncActivityAt(input: {
  status: string;
  lastIncrementalAt?: string | null;
  updatedAt?: string | null;
}): string {
  if (syncIsBusy(input.status) || input.status === "failed") {
    return input.updatedAt || input.lastIncrementalAt || "";
  }
  return input.lastIncrementalAt || input.updatedAt || "";
}

export type SyncProgressView = {
  label: string;
  fillPct: number;
  indeterminate: boolean;
  detail: string;
};

export function syncProgressView(input: {
  status: string;
  rowsDone?: number;
  rowsExpected?: number;
  rowsSynced?: number;
  entity?: string;
}): SyncProgressView {
  const done = input.rowsDone ?? 0;
  const expected = input.rowsExpected ?? 0;
  const synced = input.rowsSynced ?? 0;
  const unit = syncCountUnit(input.entity || "");
  const staleLive = syncIsBusy(input.status) && expected > 0 && done > expected;
  const pct = staleLive ? null : syncProgressPercent(done, expected, input.status);
  const indeterminate = staleLive || (syncIsBusy(input.status) && pct == null);
  let fillPct = pct ?? 0;
  if (input.status === "idle") fillPct = 0;
  if (indeterminate) fillPct = 35;
  const showLive = !staleLive && (syncIsBusy(input.status) || input.status === "failed");
  const left = showLive ? done : staleLive ? expected : synced;
  const right = staleLive ? 0 : expected;
  let detail = `${formatSyncCount(left)} ${unit}`;
  if (right > 0 && (syncIsBusy(input.status) || right !== left)) {
    detail = `${formatSyncCount(left)} / ${formatSyncCount(right)} ${unit}`;
  }
  if (pct != null) detail += ` · ${pct}%`;
  return {
    label: syncStatusLabel(input.status),
    fillPct,
    indeterminate,
    detail,
  };
}
