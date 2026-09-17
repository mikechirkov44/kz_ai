import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import AssistantLaunch from "./AssistantLaunch";

afterEach(cleanup);

describe("AssistantLaunch", () => {
  it("links to the assistant and marks the current page", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/assistant"]}>
        <AssistantLaunch />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: "Ассистент" });
    expect(link.getAttribute("href")).toBe("/assistant");
    expect(link.classList.contains("active")).toBe(true);
    expect(container.querySelector(".assistant-launch-orb")).toBeTruthy();
    expect(container).toMatchSnapshot();
  });

  it("is idle on other pages", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AssistantLaunch />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Ассистент" }).classList.contains("active")).toBe(false);
  });
});
