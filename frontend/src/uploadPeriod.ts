export function uploadPeriodLabel(row: {
  upload_type?: string | null;
  period_year?: number | null;
  period_month?: number | null;
  stock_date?: string | null;
}): string {
  const month =
    row.period_year && row.period_month
      ? `${row.period_year}-${String(row.period_month).padStart(2, "0")}`
      : "";
  const stock = row.stock_date || "";
  if (row.upload_type === "stocks" || row.upload_type === "promo_motivation") {
    return stock || month || "—";
  }
  if (row.upload_type === "both" && month && stock) {
    return `${month}, остаток ${stock}`;
  }
  return month || stock || "—";
}
