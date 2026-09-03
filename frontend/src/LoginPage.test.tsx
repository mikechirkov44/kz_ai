import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import LoginPage from "./pages/LoginPage";

describe("LoginPage", () => {
  it("renders brand title", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Акции по клиентам")).toBeTruthy();
  });
});
