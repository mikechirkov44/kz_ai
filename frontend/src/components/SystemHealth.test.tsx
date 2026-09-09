import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SystemHealth from "./SystemHealth";

describe("SystemHealth", () => {
  it("renders labeled chips from connection settings", () => {
    const { container } = render(
      <SystemHealth
        health={{
          status: "ok",
          database: "ok",
          redis: "ok",
          odata: [
            { source_id: "asil", label: "Север", status: "ok" },
            { source_id: "miamor", label: "Юг", status: "error" },
          ],
        }}
      />,
    );
    expect(screen.getByText("Состояние системы")).toBeTruthy();
    expect(screen.getByText("Север")).toBeTruthy();
    expect(screen.getByText("Юг")).toBeTruthy();
    expect(screen.queryByText("Асыл")).toBeNull();
    expect(screen.queryByText("asil")).toBeNull();
    expect(container).toMatchSnapshot();
  });

  it("shows a loading line before the first response", () => {
    render(<SystemHealth health={null} />);
    expect(screen.getByText("Проверяю…")).toBeTruthy();
  });

  it("shows the error instead of chips", () => {
    const { container } = render(<SystemHealth health={null} error="Нет связи с API" />);
    expect(container.textContent).toContain("Нет связи с API");
    expect(container.querySelector(".health-chips")).toBeNull();
  });
});
