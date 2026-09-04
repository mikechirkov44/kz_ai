import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import LoginPage from "./pages/LoginPage";

describe("LoginPage", () => {
  it("renders brand title", () => {
    const { container } = render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(container).toMatchSnapshot();
  });
});
