import { describe, expect, it } from "vitest";
import { healthStatusLabel, healthStatusTone, systemHealthChips, type SystemHealthPayload } from "./systemHealth";

const sample: SystemHealthPayload = {
  status: "ok",
  database: "ok",
  redis: "error",
  odata: [
    { source_id: "asil", label: "Асыл", status: "ok" },
    { source_id: "miamor", label: "МиАмор", status: "disabled" },
  ],
};

describe("systemHealth", () => {
  it("maps statuses to Russian labels and tones", () => {
    expect(healthStatusLabel("ok")).toBe("ок");
    expect(healthStatusLabel("error")).toBe("ошибка");
    expect(healthStatusLabel("unconfigured")).toBe("нет настроек");
    expect(healthStatusLabel("mystery")).toBe("mystery");
    expect(healthStatusTone("ok")).toBe("ok");
    expect(healthStatusTone("error")).toBe("bad");
    expect(healthStatusTone("disabled")).toBe("warn");
  });

  it("builds chips from connection labels, not hardcoded ids", () => {
    const chips = systemHealthChips(sample, true);
    expect(chips.map((chip) => chip.name)).toEqual(["API", "База", "Redis", "Асыл", "МиАмор"]);
    expect(chips.find((chip) => chip.key === "redis")?.tone).toBe("bad");
    expect(chips.find((chip) => chip.name === "МиАмор")?.statusLabel).toBe("выкл");
    expect(chips.some((chip) => chip.name === "asil")).toBe(false);
  });

  it("shows API error when the check did not reach the server", () => {
    expect(systemHealthChips(null, false)).toEqual([
      { key: "api", name: "API", statusLabel: "ошибка", tone: "bad" },
    ]);
  });
});
