import { describe, expect, it } from "vitest";
import { uploadPeriodLabel } from "./uploadPeriod";

describe("uploadPeriodLabel", () => {
  it("shows the stock date for stock files even when a month was stored", () => {
    expect(
      uploadPeriodLabel({
        upload_type: "stocks",
        period_year: 2025,
        period_month: 8,
        stock_date: "2025-11-01",
      }),
    ).toBe("2025-11-01");
  });

  it("keeps year and month for sales", () => {
    expect(uploadPeriodLabel({ upload_type: "sales", period_year: 2025, period_month: 10 })).toBe("2025-10");
  });
});
