import { describe, expect, it } from "vitest";
import { lastPage, pageRangeLabel } from "./pageRange";

describe("pageRange", () => {
  it("shows the visible slice", () => {
    expect(pageRangeLabel(1, 216)).toBe("1–50 из 216");
    expect(pageRangeLabel(5, 216)).toBe("201–216 из 216");
    expect(pageRangeLabel(1, 0)).toBe("нет записей");
  });

  it("computes the last page", () => {
    expect(lastPage(216)).toBe(5);
    expect(lastPage(0)).toBe(1);
    expect(lastPage(50)).toBe(1);
  });
});
