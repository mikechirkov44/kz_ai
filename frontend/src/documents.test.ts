import { describe, expect, it } from "vitest";
import {
  docTypeLabel,
  documentJournalDetailUrl,
  documentJournalListUrl,
  documentListNumber,
  documentTotalQuantity,
  linesQuantity,
} from "./documents";

describe("documents", () => {
  it("maps API types to Russian labels", () => {
    expect(docTypeLabel("return")).toBe("Возврат");
    expect(docTypeLabel("realization")).toBe("Реализация");
    expect(docTypeLabel("order")).toBe("Заказ");
    expect(docTypeLabel("production")).toBe("Поступление продукции из производства");
    expect(docTypeLabel("goods")).toBe("Поступление товаров и услуг");
    expect(docTypeLabel("")).toBe("");
    expect(docTypeLabel("unknown")).toBe("unknown");
  });

  it("builds production journal URLs with 1C doc type", () => {
    const production = { endpoint: "production", docType: "production" as const };
    const goods = { endpoint: "production", docType: "goods" as const };
    expect(documentJournalListUrl(production, new URLSearchParams({ page: "1" }))).toBe(
      "/api/v1/documents/production?page=1&doc_type=production",
    );
    expect(documentJournalListUrl(goods, new URLSearchParams({ page: "1" }))).toBe(
      "/api/v1/documents/production?page=1&doc_type=goods",
    );
    expect(documentJournalDetailUrl(goods, "asil", "ref-1")).toBe(
      "/api/v1/documents/production/asil/ref-1",
    );
  });

  it("sums line quantities and ignores missing API total", () => {
    const lines = [{ quantity: 1 }, { quantity: 1 }, { quantity: 1 }];
    expect(linesQuantity(lines)).toBe(3);
    expect(documentTotalQuantity(0, lines)).toBe(3);
    expect(documentTotalQuantity(undefined, lines)).toBe(3);
    expect(documentTotalQuantity(5, [])).toBe(5);
    expect(documentTotalQuantity(undefined, undefined)).toBe(0);
  });

  it("shows document number instead of 1C guid fragment", () => {
    expect(documentListNumber({ doc_number: "ПР-000012" })).toBe("ПР-000012");
    expect(documentListNumber({ doc_number: "  42  " })).toBe("42");
    expect(documentListNumber({ doc_number: "" })).toBe("—");
    expect(documentListNumber({ doc_number: null })).toBe("—");
    expect(documentListNumber({})).toBe("—");
  });
});
