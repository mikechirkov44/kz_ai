import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RowActionsMenu from "./RowActionsMenu";

describe("RowActionsMenu", () => {
  it("opens a menu and runs the chosen action", () => {
    const onDelete = vi.fn();
    const { container } = render(
      <RowActionsMenu
        items={[
          { id: "file", label: "Файл", onSelect: () => undefined },
          { id: "delete", label: "Удалить", danger: true, onSelect: onDelete },
        ]}
      />,
    );
    expect(screen.queryByRole("menu")).toBeNull();
    expect(container).toMatchSnapshot();

    fireEvent.click(screen.getByRole("button", { name: "Действия" }));
    const menu = screen.getByRole("menu");
    expect(menu.parentElement).toBe(document.body);
    fireEvent.click(screen.getByRole("menuitem", { name: "Удалить" }));
    expect(onDelete).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
