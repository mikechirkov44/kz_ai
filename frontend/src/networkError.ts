export function networkErrorMessage(err: unknown): string {
  const name = err instanceof Error ? err.name : "";
  if (name === "AbortError") {
    return "Запрос отменён";
  }
  if (err instanceof TypeError) {
    const text = err.message.toLowerCase();
    if (text.includes("failed to fetch") || text.includes("networkerror") || text.includes("load failed")) {
      return "Нет связи с сервером. Если отчёт тяжёлый — подождите и нажмите «Показать» ещё раз.";
    }
    return "Нет связи с сервером. Обновите страницу или повторите действие.";
  }
  return err instanceof Error ? err.message : "Ошибка сети";
}
