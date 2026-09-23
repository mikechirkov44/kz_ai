import { describe, expect, it } from "vitest";
import { uploadDeleteConfirm } from "./uploadActions";

describe("uploadDeleteConfirm", () => {
  it("asks to roll back rows for one data file", () => {
    expect(uploadDeleteConfirm([{ file_name: "остатки.xlsx", upload_type: "stocks" }])).toBe(
      "Удалить «остатки.xlsx» и строки, которые он загрузил?",
    );
  });

  it("keeps quarterly plan amounts when that file is deleted", () => {
    expect(uploadDeleteConfirm([{ file_name: "план.xlsx", upload_type: "quarterly_plans" }])).toContain(
      "Суммы квартальных планов не изменятся",
    );
  });

  it("counts a bulk delete", () => {
    expect(
      uploadDeleteConfirm([
        { file_name: "a.xlsx", upload_type: "sales" },
        { file_name: "b.xlsx", upload_type: "stocks" },
      ]),
    ).toContain("(2)");
  });
});
