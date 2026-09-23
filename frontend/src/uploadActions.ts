export function uploadDeleteConfirm(rows: { file_name: string; upload_type: string }[]): string {
  if (rows.length === 1) {
    const row = rows[0];
    return row.upload_type === "quarterly_plans"
      ? `Удалить «${row.file_name}» из истории? Суммы квартальных планов не изменятся.`
      : `Удалить «${row.file_name}» и строки, которые он загрузил?`;
  }
  const plans = rows.some((row) => row.upload_type === "quarterly_plans");
  const count = rows.length;
  return plans
    ? `Удалить выбранные загрузки (${count})? Суммы квартальных планов не изменятся.`
    : `Удалить выбранные загрузки (${count}) и строки, которые они загрузили?`;
}
