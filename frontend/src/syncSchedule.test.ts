import { describe, expect, it } from "vitest";
import {
  applyScheduleFrequency,
  DEFAULT_RUN_AT,
  scheduleFrequencyValue,
  SYNC_AT_TIME,
  syncScheduleEnvHint,
  toggleWeekday,
} from "./syncSchedule";

describe("syncSchedule", () => {
  it("toggles weekdays and keeps at least one day", () => {
    expect(toggleWeekday([0, 1], 2)).toEqual([0, 1, 2]);
    expect(toggleWeekday([0, 1], 1)).toEqual([0]);
    expect(toggleWeekday([0], 0)).toEqual([0]);
  });

  it("explains env kill switch", () => {
    expect(syncScheduleEnvHint(false, "Asia/Almaty")).toContain("SYNC_ENABLED");
    expect(syncScheduleEnvHint(true, "Asia/Almaty")).toContain("Полная синхронизация только вручную");
  });

  it("switches between interval and clock time", () => {
    expect(scheduleFrequencyValue({ mode: "interval", interval_minutes: 30 })).toBe("30");
    expect(scheduleFrequencyValue({ mode: SYNC_AT_TIME, interval_minutes: 15 })).toBe(SYNC_AT_TIME);
    expect(applyScheduleFrequency({ mode: "interval", interval_minutes: 15 }, SYNC_AT_TIME)).toEqual({
      mode: SYNC_AT_TIME,
      interval_minutes: 15,
      run_at: DEFAULT_RUN_AT,
    });
    expect(applyScheduleFrequency({ mode: SYNC_AT_TIME, interval_minutes: 15, run_at: "04:10" }, "60")).toEqual({
      mode: "interval",
      interval_minutes: 60,
      run_at: "04:10",
    });
  });
});
