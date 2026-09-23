export type AssistantStatus = "ok" | "error" | "off";
export type AssistantMode = "service" | "onec";

export type AssistantTool = {
  name: string;
  label: string;
};

export type AssistantFactRow = {
  rank: number;
  title: string;
  hint?: string | null;
  quantity?: number | null;
  amount?: number | null;
  percent?: number | null;
  rank_delta?: number | null;
  prev_rank?: number | null;
  is_new?: boolean;
  prompt?: string;
};

export type AssistantFactCard = {
  tool?: string;
  title: string;
  period?: string | null;
  rows: AssistantFactRow[];
};

export type AssistantFollowUp = {
  label: string;
  prompt: string;
};

export type AssistantReply = {
  status: AssistantStatus;
  answer: string;
  error?: string | null;
  mode?: AssistantMode;
  tools?: AssistantTool[];
  facts?: AssistantFactCard[];
  follow_ups?: AssistantFollowUp[];
  period?: { year: number; quarter: number };
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools?: AssistantTool[];
  facts?: AssistantFactCard[];
  followUps?: AssistantFollowUp[];
  error?: string;
};

export const ASSISTANT_MODES = [
  { id: "service" as const, label: "Сервис", hint: "Excel, план и отгрузки из нашей базы" },
  { id: "onec" as const, label: "1С", hint: "Живые документы из баз 1С" },
];

export const ASSISTANT_CHIPS = [
  { label: "Топ-5 артикулов", prompt: "Топ-5 продаваемых артикулов за текущий квартал" },
  { label: "Топ по отгрузке", prompt: "Топ-5 артикулов по отгрузке 1С за текущий квартал" },
  { label: "Топ клиентов", prompt: "Топ-5 клиентов по продажам Excel за текущий квартал" },
  { label: "Отстают от плана", prompt: "Кто сильнее всего отстаёт от квартального плана отгрузки?" },
] as const;

export const ASSISTANT_CHIPS_ONEC = [
  { label: "Реализации", prompt: "Покажи реализации за текущий квартал" },
  { label: "Заказы", prompt: "Какие заказы клиентов есть за текущий квартал?" },
  { label: "Возвраты", prompt: "Возвраты от покупателей за текущий квартал" },
  { label: "Номенклатура", prompt: "Найди номенклатуру по запросу кольцо" },
] as const;

export const ASSISTANT_WAIT_STEPS = [
  "Смотрю продажи",
  "Сверяю отгрузки 1С",
  "Сравниваю с прошлым кварталом",
  "Пишу вывод",
] as const;

export const ASSISTANT_WAIT_STEPS_ONEC = [
  "Подключаюсь к 1С",
  "Читаю документы OData",
  "Сверяю период",
  "Пишу вывод",
] as const;

export function normalizeAssistantMode(value: unknown): AssistantMode {
  return value === "onec" ? "onec" : "service";
}

export function chipsForMode(mode: AssistantMode) {
  return mode === "onec" ? ASSISTANT_CHIPS_ONEC : ASSISTANT_CHIPS;
}

export function waitStepsForMode(mode: AssistantMode) {
  return mode === "onec" ? ASSISTANT_WAIT_STEPS_ONEC : ASSISTANT_WAIT_STEPS;
}

export function historyPayload(messages: ChatMessage[]): { role: "user" | "assistant"; content: string }[] {
  return messages
    .filter((item) => item.role === "user" || item.role === "assistant")
    .filter((item) => item.content.trim() && !item.error)
    .slice(-6)
    .map((item) => ({ role: item.role, content: item.content }));
}

export function assistantErrorText(reply: AssistantReply, fallback = "Не удалось получить ответ"): string {
  if (reply.error && reply.error.trim()) return reply.error.trim();
  if (reply.status === "off") {
    return "Языковая модель выключена в админке. Включите LLM, чтобы задавать вопросы по данным.";
  }
  return fallback;
}

export function splitAnswer(text: string): string[] {
  const trimmed = (text || "").trim();
  if (!trimmed) return [];
  const blocks = trimmed
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (blocks.length > 1) return blocks;
  const lines = trimmed
    .split("\n")
    .map((part) => part.trim())
    .filter(Boolean);
  return lines.length ? lines : [trimmed];
}

export function rankChangeLabel(
  delta?: number | null,
  _prevRank?: number | null,
  isNew = false,
): string | null {
  if (isNew) return "новый";
  if (delta == null) return null;
  if (delta === 0) return "как в прошлом кв.";
  if (delta > 0) return `↑${delta}`;
  return `↓${Math.abs(delta)}`;
}
