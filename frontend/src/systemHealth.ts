export type HealthODataItem = {
  source_id: string;
  label: string;
  status: string;
};

export type SystemHealthPayload = {
  status: string;
  database: string;
  redis: string;
  odata: HealthODataItem[];
};

export type HealthChipTone = "ok" | "warn" | "bad";

export type HealthChip = {
  key: string;
  name: string;
  statusLabel: string;
  tone: HealthChipTone;
};

const STATUS_LABELS: Record<string, string> = {
  ok: "ок",
  error: "ошибка",
  disabled: "выкл",
  unconfigured: "нет настроек",
  degraded: "сбой",
};

export function healthStatusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
}

export function healthStatusTone(status: string): HealthChipTone {
  if (status === "ok") return "ok";
  if (status === "error") return "bad";
  return "warn";
}

function chip(key: string, name: string, status: string): HealthChip {
  return {
    key,
    name,
    statusLabel: healthStatusLabel(status),
    tone: healthStatusTone(status),
  };
}

export function systemHealthChips(health: SystemHealthPayload | null, apiReachable: boolean): HealthChip[] {
  if (!apiReachable || !health) {
    return [chip("api", "API", "error")];
  }
  const odata = Array.isArray(health.odata) ? health.odata : [];
  return [
    chip("api", "API", "ok"),
    chip("database", "База", health.database),
    chip("redis", "Redis", health.redis),
    ...odata.map((item) => chip(`odata-${item.source_id}`, item.label || item.source_id, item.status)),
  ];
}
