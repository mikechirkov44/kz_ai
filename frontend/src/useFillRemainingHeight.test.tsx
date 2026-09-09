import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useFillRemainingHeight } from "./useFillRemainingHeight";

function Probe() {
  const ref = useFillRemainingHeight(16);
  return <div data-testid="pane" ref={ref} />;
}

describe("useFillRemainingHeight", () => {
  it("sets an explicit height from the viewport", () => {
    const { getByTestId } = render(<Probe />);
    const pane = getByTestId("pane");
    expect(pane.style.height).toMatch(/^\d+px$/);
    expect(Number.parseInt(pane.style.height, 10)).toBeGreaterThanOrEqual(280);
  });
});
