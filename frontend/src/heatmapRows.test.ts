import { describe, expect, it } from "vitest";
import {
  heatmapCellKey,
  heatmapDuplicateNames,
  heatmapRowLabel,
  normalizeHeatmapCounterparties,
} from "./heatmapRows";

describe("heatmapRows", () => {
  it("keeps a stable id when two clients share a name", () => {
    const rows = normalizeHeatmapCounterparties([
      { id: "a", name: "ИП Дворецкая Е.А.", source_id: "asil" },
      { id: "b", name: "ИП Дворецкая Е.А.", source_id: "miamor" },
    ]);
    expect(rows.map((row) => row.id)).toEqual(["a", "b"]);
    const dupes = heatmapDuplicateNames(rows);
    expect(heatmapRowLabel(rows[0], dupes, (id) => (id === "asil" ? "Асыл" : id))).toBe(
      "ИП Дворецкая Е.А. · Асыл",
    );
    expect(heatmapCellKey("a", "IM-001")).not.toBe(heatmapCellKey("b", "IM-001"));
  });

  it("accepts a plain name list from older payloads", () => {
    expect(normalizeHeatmapCounterparties(["ТОО Alpha"])).toEqual([{ id: "ТОО Alpha", name: "ТОО Alpha" }]);
  });
});
