export const MOTIVATION_WAIT_STEPS = [
  "Собираю продажи за месяц",
  "Считаю вознаграждение",
  "Сверяю цены с отгрузками 1С",
] as const;

export const MOTIVATION_WAIT_STEP_MS = 2200;

export function waitStepAt(
  elapsedMs: number,
  steps: readonly string[] = MOTIVATION_WAIT_STEPS,
  stepMs: number = MOTIVATION_WAIT_STEP_MS,
): string {
  if (!steps.length) return "";
  const safeStep = Math.max(1, stepMs);
  const index = Math.floor(Math.max(0, elapsedMs) / safeStep) % steps.length;
  return steps[index];
}
