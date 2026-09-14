import { describe, expect, it } from "vitest";
import { userInitials } from "./userInitials";

describe("userInitials", () => {
  it("takes two letters from a single word", () => {
    expect(userInitials("Administrator")).toBe("AD");
  });

  it("uses first and last name", () => {
    expect(userInitials("Иван Петров")).toBe("ИП");
  });

  it("uses the local part of an email", () => {
    expect(userInitials("admin@example.com")).toBe("AD");
  });

  it("falls back for empty input", () => {
    expect(userInitials("")).toBe("?");
    expect(userInitials("   ")).toBe("?");
    expect(userInitials("@")).toBe("?");
  });
});
