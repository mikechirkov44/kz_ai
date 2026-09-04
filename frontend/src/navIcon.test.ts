import { describe, expect, it } from "vitest";
import { iconForPath } from "./components/NavIcon";

describe("iconForPath", () => {
  it("maps dashboard only on root", () => {
    expect(iconForPath("/")).toBe("dashboard");
    expect(iconForPath("/motivation")).toBe("star");
  });

  it("uses longest prefix for nested quarterly", () => {
    expect(iconForPath("/quarterly")).toBe("calendar");
    expect(iconForPath("/quarterly/tz")).toBe("calendar");
  });
});
