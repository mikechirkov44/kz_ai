export const SYNC_AT_TIME = "at_time";
export const DEFAULT_RUN_AT = "03:00";

export const SYNC_FREQUENCY_OPTIONS = [
  { value: "15", label: "каждые 15 минут" },
  { value: "30", label: "каждые 30 минут" },
  { value: "60", label: "каждый час" },
  { value: "180", label: "каждые 3 часа" },
  { value: "360", label: "каждые 6 часов" },
  { value: "720", label: "каждые 12 часов" },
  { value: "1440", label: "раз в сутки" },
  { value: SYNC_AT_TIME, label: "в заданное время" },
];

export const WEEKDAY_OPTIONS = [
  { value: 0, label: "Пн" },
  { value: 1, label: "Вт" },
  { value: 2, label: "Ср" },
  { value: 3, label: "Чт" },
  { value: 4, label: "Пт" },
  { value: 5, label: "Сб" },
  { value: 6, label: "Вс" },
];

export type SyncScheduleMode = "interval" | "at_time";

export function toggleWeekday(days: number[], day: number): number[] {
  if (days.includes(day)) {
    if (days.length === 1) return days;
    return days.filter((item) => item !== day);
  }
  return [...days, day].sort((a, b) => a - b);
}

export function scheduleFrequencyValue(schedule: { mode?: string; interval_minutes: number }): string {
  return schedule.mode === SYNC_AT_TIME ? SYNC_AT_TIME : String(schedule.interval_minutes);
}

export function applyScheduleFrequency<T extends { mode?: string; interval_minutes: number; run_at?: string }>(
  prev: T,
  value: string,
): T {
  if (value === SYNC_AT_TIME) {
    return { ...prev, mode: SYNC_AT_TIME, run_at: prev.run_at || DEFAULT_RUN_AT };
  }
  return { ...prev, mode: "interval", interval_minutes: Number(value) || 15 };
}

export function syncScheduleEnvHint(envSyncEnabled: boolean, timezone: string): string {
  const zone = timezone || "Asia/Almaty";
  if (!envSyncEnabled) {
    return `Автозапуск выключен в окружении (SYNC_ENABLED). Расписание ниже не сработает, пока его не включат. Время — ${zone}. Полная синхронизация только вручную.`;
  }
  return `Автообновление по расписанию для всех включённых баз. Время — ${zone}. Полная синхронизация только вручную.`;
}
