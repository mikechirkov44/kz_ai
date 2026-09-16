import { describe, expect, it } from "vitest";
import { appendDigit, digitFromKey, stepNumber } from "./numberField";

describe("numberField", () => {
  it("steps integers with a minimum", () => {
    expect(stepNumber("1", 1, { integer: true, min: 1 })).toBe("2");
    expect(stepNumber("1", -1, { integer: true, min: 1 })).toBe("1");
  });

  it("appends keypad digits", () => {
    expect(appendDigit("", "9")).toBe("9");
    expect(appendDigit("12", "⌫")).toBe("1");
    expect(appendDigit("95", ".", false)).toBe("95.");
    expect(appendDigit("1", ".", true)).toBe("1");
  });

  it("maps keyboard keys to keypad digits", () => {
    expect(digitFromKey("7")).toBe("7");
    expect(digitFromKey("Backspace")).toBe("⌫");
    expect(digitFromKey("Delete")).toBe("⌫");
    expect(digitFromKey(",", false)).toBe(".");
    expect(digitFromKey("Decimal", false)).toBe(".");
    expect(digitFromKey(".", true)).toBe(null);
    expect(digitFromKey("Enter")).toBe(null);
  });
});
