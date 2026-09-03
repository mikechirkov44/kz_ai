import { FormEvent, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [uploadType, setUploadType] = useState("sales");
  const [stockDate, setStockDate] = useState("");
  const [result, setResult] = useState<{ status: string; processed_rows: number; errors: { row: number; field: string; message: string }[]; upload_id: string } | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError("");
    const body = new FormData();
    body.append("file", file);
    body.append("period_year", String(year));
    body.append("period_month", String(month));
    body.append("upload_type", uploadType);
    if (stockDate) body.append("stock_date", stockDate);
    const token = localStorage.getItem("access_token");
    const res = await fetch(`${API_URL}/api/v1/uploads/sales`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body,
    });
    const json = await res.json();
    if (!res.ok) {
      setError(typeof json.detail === "string" ? json.detail : JSON.stringify(json));
      return;
    }
    setResult(json);
  }

  return (
    <>
      <h1>Загрузка Excel</h1>
      <p className="muted">Продажи / остатки клиента. Пакетная валидация всех ошибок сразу.</p>
      <form className="panel" onSubmit={onSubmit}>
        {error && <div className="alert">{error}</div>}
        <div className="grid-2">
          <label className="field">Файл<input type="file" accept=".xlsx,.xls" onChange={(e) => setFile(e.target.files?.[0] || null)} required /></label>
          <label className="field">Тип
            <select value={uploadType} onChange={(e) => setUploadType(e.target.value)}>
              <option value="sales">Продажи</option>
              <option value="stocks">Остатки</option>
              <option value="both">Продажи + Остатки</option>
            </select>
          </label>
          <label className="field">Год<input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} /></label>
          <label className="field">Месяц<input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))} /></label>
          <label className="field">Дата остатков<input type="date" value={stockDate} onChange={(e) => setStockDate(e.target.value)} /></label>
        </div>
        <button className="btn" type="submit">Загрузить</button>
      </form>
      {result && (
        <div className="panel">
          <h2>Результат: {result.status}</h2>
          <p>Обработано строк: {result.processed_rows}</p>
          {!!result.errors?.length && (
            <div className="alert-list">
              {result.errors.map((err, idx) => (
                <div key={idx} className="alert">Строка {err.row}: [{err.field}] {err.message}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
