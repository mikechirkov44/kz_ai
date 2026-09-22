import { describe, expect, it } from "vitest";
import {
  OPENAI_BASE_URL,
  OPENAI_DEFAULT_MODEL,
  OPENROUTER_BASE_URL,
  OPENROUTER_DEFAULT_MODEL,
  applyLlmProvider,
  isOpenRouterModel,
  normalizeLlmProvider,
} from "./llmProvider";

describe("llmProvider", () => {
  it("normalizes stored provider and OpenAI host", () => {
    expect(normalizeLlmProvider("openai")).toBe("openai");
    expect(normalizeLlmProvider("openrouter")).toBe("openrouter");
    expect(normalizeLlmProvider("openai_compatible", "https://api.openai.com/v1")).toBe("openai");
    expect(normalizeLlmProvider("openai_compatible", "https://openrouter.ai/api/v1")).toBe("openrouter");
  });

  it("detects OpenRouter ids", () => {
    expect(isOpenRouterModel("openrouter/free")).toBe(true);
    expect(isOpenRouterModel("meta-llama/llama-3.3-70b-instruct:free")).toBe(true);
    expect(isOpenRouterModel("gpt-6-astra")).toBe(false);
  });

  it("switches defaults when changing provider", () => {
    const fromRouter = applyLlmProvider(
      { provider: "openrouter", base_url: OPENROUTER_BASE_URL, model: "openrouter/free" },
      "openai",
    );
    expect(fromRouter).toEqual({
      provider: "openai",
      base_url: OPENAI_BASE_URL,
      model: OPENAI_DEFAULT_MODEL,
    });
    const fromOpenai = applyLlmProvider(
      { provider: "openai", base_url: OPENAI_BASE_URL, model: "gpt-6-astra" },
      "openrouter",
    );
    expect(fromOpenai).toEqual({
      provider: "openrouter",
      base_url: OPENROUTER_BASE_URL,
      model: OPENROUTER_DEFAULT_MODEL,
    });
  });

  it("keeps a custom OpenAI model when staying on OpenAI defaults", () => {
    const next = applyLlmProvider(
      { provider: "openrouter", base_url: OPENROUTER_BASE_URL, model: "gpt-4o-mini" },
      "openai",
    );
    expect(next.model).toBe("gpt-4o-mini");
  });
});
