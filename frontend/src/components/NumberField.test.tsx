import { fireEvent, render } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import NumberField from "./NumberField";

function Host({ integer = false }: { integer?: boolean }) {
  const [value, setValue] = useState("");
  return <NumberField value={value} onChange={setValue} integer={integer} />;
}

describe("NumberField", () => {
  it("renders the stepper closed", () => {
    const { container } = render(<NumberField value="5" onChange={() => undefined} integer />);
    expect(container.querySelector(".ui-number-value")?.textContent).toContain("5");
    expect(document.querySelector(".ui-keypad")).toBeNull();
    expect(container).toMatchSnapshot();
  });

  it("types digits from the keyboard when the keypad is open", () => {
    const { container } = render(<Host integer />);
    fireEvent.click(container.querySelector(".ui-number-value")!);
    expect(document.querySelector(".ui-keypad")).toBeTruthy();
    fireEvent.keyDown(document, { key: "5" });
    fireEvent.keyDown(document, { key: "0" });
    expect(container.querySelector(".ui-number-value")?.textContent).toContain("50");
    fireEvent.keyDown(document, { key: "Backspace" });
    expect(container.querySelector(".ui-number-value")?.textContent).toContain("5");
    fireEvent.keyDown(document, { key: "Enter" });
    expect(document.querySelector(".ui-keypad")).toBeNull();
  });
});
