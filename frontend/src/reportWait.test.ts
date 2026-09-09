import { describe, expect, it } from "vitest";
import { MOTIVATION_WAIT_STEPS, waitStepAt } from "./reportWait";

describe("reportWait", () => {
  it("cycles motivation steps", () => {
    expect(waitStepAt(0)).toBe(MOTIVATION_WAIT_STEPS[0]);
    expect(waitStepAt(2199)).toBe(MOTIVATION_WAIT_STEPS[0]);
    expect(waitStepAt(2200)).toBe(MOTIVATION_WAIT_STEPS[1]);
    expect(waitStepAt(4400)).toBe(MOTIVATION_WAIT_STEPS[2]);
    expect(waitStepAt(6600)).toBe(MOTIVATION_WAIT_STEPS[0]);
  });

  it("handles empty steps", () => {
    expect(waitStepAt(1000, [])).toBe("");
  });
});
