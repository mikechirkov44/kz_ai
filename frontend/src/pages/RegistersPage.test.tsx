import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RegisterTable, registerShopLabel, type RegisterRow } from "./RegistersPage";

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

const props = {
  kind: "sales" as const,
  editingId: null,
  draft: null,
  busyId: "",
  onDraft: () => undefined,
  onEdit: () => undefined,
  onCancel: () => undefined,
  onSave: () => undefined,
  onDelete: () => undefined,
};

describe("RegisterTable", () => {
  it("shows a sales line as text with a row menu", () => {
    const { container } = render(<RegisterTable {...props} rows={[row]} />);
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByLabelText("Действия")).toBeTruthy();
    expect(container).toMatchSnapshot();
  });

  it("hides a stored nan shop", () => {
    expect(registerShopLabel("nan")).toBe("");
    render(<RegisterTable {...props} rows={[{ ...row, shop: "nan" }]} />);
    expect(screen.queryByText("nan")).toBeNull();
  });

  it("shows inputs only for the row being edited", () => {
    render(
      <RegisterTable
        {...props}
        editingId={row.id}
        draft={{ article: row.article, shop: "Молл", quantity: "2" }}
        rows={[row]}
      />,
    );
    expect(screen.getByLabelText("Артикул ТОО Азамат - Золото")).toBeTruthy();
    expect(screen.getByLabelText("Магазин ТОО Азамат - Золото")).toBeTruthy();
  });
});
