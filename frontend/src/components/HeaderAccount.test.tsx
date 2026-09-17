import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import HeaderAccount from "./HeaderAccount";

afterEach(cleanup);

function Path() {
  const { pathname } = useLocation();
  return <span data-testid="path">{pathname}</span>;
}

function mount() {
  localStorage.setItem("access_token", "tok");
  localStorage.setItem("refresh_token", "ref");
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route
          path="/"
          element={
            <>
              <HeaderAccount name="Иван Петров" email="ivan@test.local" roleLabel="Менеджер" />
              <Path />
            </>
          }
        />
        <Route path="/login" element={<Path />} />
        <Route path="/change-password" element={<Path />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("HeaderAccount", () => {
  it("shows the user and opens change-password", () => {
    const { container } = mount();
    expect(screen.getByText("Иван Петров")).toBeTruthy();
    expect(screen.getByText("Менеджер")).toBeTruthy();
    expect(screen.getByText("ИП")).toBeTruthy();
    expect(container).toMatchSnapshot();
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    expect(screen.getByTestId("path").textContent).toBe("/change-password");
  });

  it("clears the session and goes to login", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Выйти" }));
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(screen.getByTestId("path").textContent).toBe("/login");
  });
});
