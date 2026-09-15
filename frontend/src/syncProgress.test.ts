import { describe, expect, it } from "vitest";
import {
  formatSyncCount,
  allVisibleSelected,
  setVisibleSelection,
  syncActivityAt,
  syncCountUnit,
  syncIsBusy,
  syncProgressPercent,
  syncProgressView,
  syncRowKey,
  syncStatusLabel,
} from "./syncProgress";

describe("syncProgress", () => {
  it("labels known statuses", () => {
    expect(syncStatusLabel("queued")).toBe("в очереди");
    expect(syncStatusLabel("running")).toBe("выполняется");
    expect(syncStatusLabel("weird")).toBe("weird");
  });

  it("builds a stable row key", () => {
    expect(syncRowKey("asil", "realization")).toBe("asil:realization");
  });

  it("selects and clears visible sync rows", () => {
    expect(allVisibleSelected(["asil:nomenclature"], ["asil:nomenclature", "asil:realization"])).toBe(false);
    expect(allVisibleSelected(["a", "b"], ["a", "b"])).toBe(true);
    expect(allVisibleSelected([], [])).toBe(false);
    expect(setVisibleSelection(["keep:x", "asil:nomenclature"], ["asil:nomenclature", "asil:realization"], true)).toEqual([
      "keep:x",
      "asil:nomenclature",
      "asil:realization",
    ]);
    expect(setVisibleSelection(["keep:x", "asil:nomenclature"], ["asil:nomenclature", "asil:realization"], false)).toEqual([
      "keep:x",
    ]);
  });

  it("caps running percent below 100 until success", () => {
    expect(syncProgressPercent(0, 0, "running")).toBeNull();
    expect(syncProgressPercent(40, 80, "running")).toBe(50);
    expect(syncProgressPercent(90, 80, "running")).toBe(99);
    expect(syncProgressPercent(90, 80, "success")).toBe(100);
  });

  it("formats a two-tone running view", () => {
    const view = syncProgressView({
      status: "running",
      entity: "realization",
      rowsDone: 250,
      rowsExpected: 1000,
      rowsSynced: 1000,
    });
    expect(view.label).toBe("выполняется");
    expect(view.fillPct).toBe(25);
    expect(view.indeterminate).toBe(false);
    expect(view.detail).toContain("документов");
    expect(view.detail).toContain("%");
    expect(syncIsBusy("queued")).toBe(true);
    expect(syncIsBusy("success")).toBe(false);
    expect(formatSyncCount(1234)).toMatch(/1/);
  });

  it("uses a pulse fill when expected is unknown", () => {
    const view = syncProgressView({
      status: "running",
      entity: "nomenclature",
      rowsDone: 12,
      rowsExpected: 0,
      rowsSynced: 0,
    });
    expect(view.indeterminate).toBe(true);
    expect(view.fillPct).toBe(35);
    expect(view.detail).toContain("записей");
  });

  it("labels journals as documents and catalogs as records", () => {
    expect(syncCountUnit("production_receipt")).toBe("документов");
    expect(syncCountUnit("counterparty")).toBe("записей");
  });

  it("ignores a live counter that overshoots stored documents", () => {
    const view = syncProgressView({
      status: "running",
      entity: "realization",
      rowsDone: 11200,
      rowsExpected: 5350,
      rowsSynced: 5350,
    });
    expect(view.indeterminate).toBe(true);
    expect(view.detail).toMatch(/5.350 документов/);
    expect(view.detail).not.toContain("%");
    expect(view.detail).not.toMatch(/11/);
  });

  it("prefers heartbeat time while a row is busy or failed", () => {
    expect(
      syncActivityAt({
        status: "running",
        lastIncrementalAt: "2026-09-14T14:02:00Z",
        updatedAt: "2026-09-14T14:30:00Z",
      }),
    ).toBe("2026-09-14T14:30:00Z");
    expect(
      syncActivityAt({
        status: "failed",
        lastIncrementalAt: "2026-09-04T12:00:00Z",
        updatedAt: "2026-09-14T12:17:00Z",
      }),
    ).toBe("2026-09-14T12:17:00Z");
    expect(
      syncActivityAt({
        status: "success",
        lastIncrementalAt: "2026-09-14T17:11:00Z",
        updatedAt: "2026-09-14T17:12:00Z",
      }),
    ).toBe("2026-09-14T17:11:00Z");
  });
});
