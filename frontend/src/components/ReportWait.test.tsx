import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ReportWait from "./ReportWait";

describe("ReportWait", () => {
  it("shows the first status step", () => {
    const { container } = render(<ReportWait />);
    expect(screen.getByText("Считаю мотивацию")).toBeTruthy();
    expect(screen.getByText("Собираю продажи за месяц")).toBeTruthy();
    expect(container).toMatchSnapshot();
  });

  it("renders a compact refresh banner", () => {
    const { container } = render(<ReportWait compact title="Обновляю отчёт" />);
    expect(container.querySelector(".report-wait.is-compact")).toBeTruthy();
    expect(screen.getByText("Обновляю отчёт")).toBeTruthy();
  });
});
