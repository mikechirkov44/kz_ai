import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import NavIcon, { iconForPath, NAV_ICON_NAMES } from "./components/NavIcon";

afterEach(cleanup);

describe("iconForPath", () => {
  it("maps dashboard only on root", () => {
    expect(iconForPath("/")).toBe("dashboard");
    expect(iconForPath("/recommendations")).toBe("bulb");
    expect(iconForPath("/assistant")).toBe("chat");
    expect(iconForPath("/settings")).toBe("palette");
  });

  it("uses longest prefix for nested quarterly", () => {
    expect(iconForPath("/quarterly")).toBe("calendar");
    expect(iconForPath("/quarterly/tz")).toBe("calendar");
  });

  it("renders a remix path for every nav glyph", () => {
    for (const name of NAV_ICON_NAMES) {
      const { container } = render(<NavIcon name={name} />);
      const path = container.querySelector("path");
      expect(path?.getAttribute("d")).toBeTruthy();
      cleanup();
    }
  });
});
