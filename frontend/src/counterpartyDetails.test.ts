import { describe, expect, it } from "vitest";
import {
  counterpartyMainRows,
  extraPropertyRows,
  headCounterpartyDisplay,
} from "./counterpartyDetails";
import { visibleDetailRows } from "./nomenclatureDetails";

describe("counterpartyDetails", () => {
  it("hides empty card fields and unchecked buyer/supplier", () => {
    const rows = visibleDetailRows(
      counterpartyMainRows({
        name: 'ИП "АСЕЛЬ"',
        full_name: 'ИП "АСЕЛЬ"',
        code: "БП595",
        legal_status: "Физ. лицо",
        is_buyer: true,
        is_supplier: false,
        parent_name: "Покупатели",
      }),
    );
    expect(rows.map((row) => row.label)).toEqual([
      "Наименование",
      "Полное наименование",
      "Код",
      "Группа",
      "Головной контрагент",
      "Правовой статус",
      "Покупатель",
    ]);
    expect(rows.find((row) => row.label === "Покупатель")?.text).toBe("да");
    expect(rows.find((row) => row.label === "Головной контрагент")?.text).toBe("—");
  });

  it("shows the head counterparty name or self", () => {
    expect(
      headCounterpartyDisplay({
        id: "1",
        name: "ИП Магазин",
        head_counterparty_id: "2",
        head_name: "ИП Головной",
      }),
    ).toBe("ИП Головной");
    expect(
      headCounterpartyDisplay({
        id: "1",
        name: "ИП Головной",
        head_counterparty_id: "1",
        head_name: "ИП Головной",
      }),
    ).toBe("он же");
    expect(headCounterpartyDisplay({ name: "ИП Магазин" })).toBeNull();
  });

  it("lists filled extra properties and skips promo", () => {
    expect(
      extraPropertyRows({
        ID_Битрикс24: "3381",
        "Участвует в акции": "да",
        Пусто: "  ",
      }),
    ).toEqual([{ label: "ID_Битрикс24", text: "3381", always: false }]);
    expect(extraPropertyRows(null)).toEqual([]);
  });
});
