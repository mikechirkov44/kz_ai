import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ChartWait from "./ChartWait";

describe("ChartWait", () => {
  it("shows the chart loading phrase", () => {
    const { container } = render(<ChartWait label="Считаю план и факт по неделям" />);
    expect(screen.getByRole("status").textContent).toContain("Считаю план и факт по неделям");
    expect(container.querySelectorAll(".chart-wait-bars span")).toHaveLength(5);
    expect(container).toMatchSnapshot();
  });
});
