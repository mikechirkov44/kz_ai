export const LLM_PROVIDERS = ["openrouter", "openai"] as const;

export type LlmProvider = (typeof LLM_PROVIDERS)[number];

export const OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1";
export const OPENAI_BASE_URL = "https://api.openai.com/v1";
export const OPENROUTER_DEFAULT_MODEL = "openrouter/free";
export const OPENAI_DEFAULT_MODEL = "gpt-6-astra";

export const LLM_PROVIDER_OPTIONS = [
  { value: "openrouter", label: "OpenRouter" },
  { value: "openai", label: "OpenAI (личный кабинет API)" },
] as const;

export function normalizeLlmProvider(provider: string, baseUrl = ""): LlmProvider {
  const value = (provider || "").trim().toLowerCase();
  if (value === "openai") return "openai";
  if (value === "openrouter") return "openrouter";
  const host = baseUrl.toLowerCase();
  if (host.includes("api.openai.com")) return "openai";
  return "openrouter";
}

export function isOpenRouterModel(model: string): boolean {
  const ident = (model || "").trim().toLowerCase();
  return ident.includes("/") || ident.endsWith(":free") || ident.startsWith("openrouter");
}

export function applyLlmProvider<T extends { provider: string; base_url: string; model: string }>(
  prev: T,
  provider: LlmProvider,
): T {
  if (provider === "openai") {
    return {
      ...prev,
      provider,
      base_url: OPENAI_BASE_URL,
      model: isOpenRouterModel(prev.model) ? OPENAI_DEFAULT_MODEL : prev.model || OPENAI_DEFAULT_MODEL,
    };
  }
  return {
    ...prev,
    provider,
    base_url: OPENROUTER_BASE_URL,
    model: isOpenRouterModel(prev.model) ? prev.model || OPENROUTER_DEFAULT_MODEL : OPENROUTER_DEFAULT_MODEL,
  };
}
