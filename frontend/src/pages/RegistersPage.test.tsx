import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RegisterLineCard, RegisterTable, registerShopLabel, type RegisterRow } from "./RegistersPage";

const row: RegisterRow = {
  id: "1",
  counterparty_name: "ТОО Азамат - Золото",
  article: "П0581-320",
  shop: "пр.Победы 65",
  quantity: 1,
  price: 78713,
  period_year: 2025,
  period_month: 10,
};

describe("RegisterTable", () => {
  it("shows a sales line and opens it on click", () => {
    const onOpen = vi.fn();
    const { container } = render(<RegisterTable kind="sales" rows={[row]} onOpen={onOpen} />);
    expect(screen.queryByRole("textbox")).toBeNull();
    screen.getByText("ТОО Азамат - Золото").click();
    expect(onOpen).toHaveBeenCalledWith(row);
    expect(container).toMatchSnapshot();
  });

  it("hides a stored nan shop", () => {
    expect(registerShopLabel("nan")).toBe("");
    render(<RegisterTable kind="sales" rows={[{ ...row, shop: "nan" }]} onOpen={() => undefined} />);
    expect(screen.queryByText("nan")).toBeNull();
  });

  it("edits the line inside the card", () => {
    render(<RegisterLineCard kind="sales" row={{ ...row, shop: "nan" }} busy={false} onSave={() => undefined} onDelete={() => undefined} />);
    expect(screen.getByLabelText("Артикул")).toBeTruthy();
    expect(screen.getByLabelText("Магазин")).toHaveProperty("value", "");
    const price = screen.getByLabelText("Цена") as HTMLInputElement;
    expect(price.readOnly).toBe(false);
    expect(price.value).toBe("78713");
  });
});
