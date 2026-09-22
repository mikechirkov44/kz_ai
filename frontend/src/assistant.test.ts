import { describe, expect, it } from "vitest";
import {
  assistantErrorText,
  chipsForMode,
  historyPayload,
  normalizeAssistantMode,
  rankChangeLabel,
  splitAnswer,
  waitStepsForMode,
  type ChatMessage,
} from "./assistant";

describe("assistant helpers", () => {
  it("keeps last six non-empty turns", () => {
    const messages: ChatMessage[] = Array.from({ length: 8 }, (_, index) => ({
      id: String(index),
      role: index % 2 === 0 ? "user" : "assistant",
      content: `m${index}`,
    }));
    expect(historyPayload(messages)).toHaveLength(6);
    expect(historyPayload(messages)[0].content).toBe("m2");
  });

  it("prefers server error text", () => {
    expect(assistantErrorText({ status: "error", answer: "", error: "Модель не ответила" })).toBe(
      "Модель не ответила",
    );
    expect(assistantErrorText({ status: "off", answer: "" })).toContain("выключена");
  });

  it("splits answers into beats", () => {
    expect(splitAnswer("Первый\n\nВторой")).toEqual(["Первый", "Второй"]);
    expect(splitAnswer("  ")).toEqual([]);
  });

  it("splits chips and wait phrases by mode", () => {
    expect(normalizeAssistantMode("onec")).toBe("onec");
    expect(normalizeAssistantMode("service")).toBe("service");
    expect(chipsForMode("service")[0].label).toContain("артикул");
    expect(chipsForMode("onec").map((item) => item.label)).toContain("Реализации");
    expect(waitStepsForMode("onec")[0]).toContain("1С");
  });

  it("labels rank movement", () => {
    expect(rankChangeLabel(2, 3)).toBe("↑2");
    expect(rankChangeLabel(-1, 1)).toBe("↓1");
    expect(rankChangeLabel(0, 1)).toBe("как в прошлом кв.");
    expect(rankChangeLabel(null, null)).toBeNull();
    expect(rankChangeLabel(null, null, true)).toBe("новый");
  });
});
