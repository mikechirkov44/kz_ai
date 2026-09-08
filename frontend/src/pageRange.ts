export const DEFAULT_PAGE_SIZE = 50;

export function pageRangeLabel(page: number, total: number, pageSize = DEFAULT_PAGE_SIZE): string {
  if (total <= 0) return "нет записей";
  const safePage = Math.max(page, 1);
  const from = (safePage - 1) * pageSize + 1;
  const to = Math.min(safePage * pageSize, total);
  return `${from}–${to} из ${total}`;
}

export function lastPage(total: number, pageSize = DEFAULT_PAGE_SIZE): number {
  if (total <= 0) return 1;
  return Math.ceil(total / pageSize);
}
