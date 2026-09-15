import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Checkbox from "./Checkbox";

describe("Checkbox", () => {
  it("renders an unchecked box with a label", () => {
    const { container } = render(
      <Checkbox checked={false} onChange={() => undefined}>
        Включено
      </Checkbox>,
    );
    const input = screen.getByRole("checkbox", { name: "Включено" });
    expect(input).toBeTruthy();
    expect((input as HTMLInputElement).checked).toBe(false);
    expect(container.querySelector(".ui-check")?.classList.contains("is-on")).toBe(false);
    expect(container).toMatchSnapshot();
  });

  it("renders a checked box", () => {
    const { container } = render(
      <Checkbox checked onChange={() => undefined} aria-label="Выбрать номенклатуру" />,
    );
    const input = screen.getByRole("checkbox", { name: "Выбрать номенклатуру" });
    expect((input as HTMLInputElement).checked).toBe(true);
    expect(container.querySelector(".ui-check")?.classList.contains("is-on")).toBe(true);
    expect(container.querySelector(".ui-check")?.classList.contains("is-bare")).toBe(true);
    expect(container).toMatchSnapshot();
  });

  it("notifies onChange when clicked", () => {
    const onChange = vi.fn();
    render(
      <Checkbox checked={false} onChange={onChange}>
        Только акция
      </Checkbox>,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Только акция" }));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("does not notify onChange when disabled", () => {
    const onChange = vi.fn();
    const { container } = render(
      <Checkbox checked={false} disabled onChange={onChange}>
        Заблокировано
      </Checkbox>,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Заблокировано" }));
    expect(onChange).not.toHaveBeenCalled();
    expect(container.querySelector(".ui-check")?.classList.contains("is-disabled")).toBe(true);
    expect(container).toMatchSnapshot();
  });

  it("stops click bubbling when onClick is set", () => {
    const onRowClick = vi.fn();
    const onChange = vi.fn();
    render(
      <div onClick={onRowClick}>
        <Checkbox checked={false} onChange={onChange} onClick={(e) => e.stopPropagation()} aria-label="Строка" />
      </div>,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Строка" }));
    expect(onChange).toHaveBeenCalledWith(true);
    expect(onRowClick).not.toHaveBeenCalled();
  });
});
