import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import PageHeader from "./PageHeader";

afterEach(cleanup);

describe("PageHeader", () => {
  it("sends the section icon and logo slot home and shows the assistant", () => {
    render(
      <MemoryRouter initialEntries={["/motivation"]}>
        <PageHeader title="Мотивация" subtitle="Бонус" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "На главную" }).getAttribute("href")).toBe("/");
    expect(screen.getByRole("link", { name: "Ассистент" }).getAttribute("href")).toBe("/assistant");
  });

  it("hides chrome on the password page", () => {
    render(
      <MemoryRouter initialEntries={["/change-password"]}>
        <PageHeader title="Смена пароля" chrome={false} />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("link", { name: "Ассистент" })).toBeNull();
  });
});
