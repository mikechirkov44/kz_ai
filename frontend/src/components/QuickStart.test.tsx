import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import QuickStart from "./QuickStart";
import { QUICK_START_KEY_PREFIX } from "../quickStart";

describe("QuickStart", () => {
  afterEach(() => {
    localStorage.removeItem(`${QUICK_START_KEY_PREFIX}u1`);
  });

  it("shows role defaults and saves a custom set", () => {
    const { container } = render(
      <MemoryRouter>
        <QuickStart userId="u1" role="manager" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Мотивация" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Администрирование" })).toBeNull();
    expect(container).toMatchSnapshot();

    fireEvent.click(screen.getByRole("button", { name: "Настроить" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Мотивация" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Оборачиваемость" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(screen.queryByRole("link", { name: "Мотивация" })).toBeNull();
    expect(screen.getByRole("link", { name: "Оборачиваемость" })).toBeTruthy();
  });
});
