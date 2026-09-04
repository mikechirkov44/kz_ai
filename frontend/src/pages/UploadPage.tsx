import { FormEvent, useState } from "react";
import { api, downloadFile } from "../api";
import DatePicker from "../components/DatePicker";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [uploadType, setUploadType] = useState("sales");
  const [stockDate, setStockDate] = useState("");
  const [result, setResult] = useState<{
    status: string;
    processed_rows: number;
    errors: { row: number; field: string; message: string }[];
    upload_id: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError("");
    setLoading(true);
    const body = new FormData();
    body.append("file", file);
    body.append("period_year", String(year));
    body.append("period_month", String(month));
    body.append("upload_type", uploadType);
    if (stockDate) body.append("stock_date", stockDate);
    try {
      const path =
        uploadType === "promo_motivation"
          ? "/api/v1/uploads/promo-motivation"
          : "/api/v1/uploads/sales";
      const json = await api<{
        status: string;
        processed_rows: number;
        errors: { row: number; field: string; message: string }[];
        upload_id: string;
      }>(path, { method: "POST", body });
      setResult(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }

  async function downloadTemplate(type: string) {
    setError("");
    try {
      await downloadFile(`/api/v1/uploads/templates/${type}`, `template_${type}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось скачать шаблон");
    }
  }

  async function downloadErrors() {
    if (!result?.upload_id) return;
    setError("");
    try {
      await downloadFile(
        `/api/v1/uploads/${result.upload_id}/errors.xlsx`,
        `errors_${result.upload_id}.xlsx`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось скачать ошибки");
    }
  }

  return (
    <>
      <PageHeader
        title="Загрузка Excel"
        subtitle="Скачайте шаблон формы, заполните и загрузите. Участники акции помечаются автоматически."
      />
      <div className="panel">
        <h2>Шаблоны форм</h2>
        <p className="muted">Колонки как в ТЗ: Головной контрагент, Артикул, Магазин, Количество [, Цена продажи]</p>
        <div className="toolbar">
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("sales")}>
            Шаблон продаж
          </button>
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("stocks")}>
            Шаблон остатков
          </button>
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("both")}>
            Шаблон продажи+остатки
          </button>
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("promo_motivation")}>
            Шаблон доп. мотивации
          </button>
        </div>
      </div>
      <form className="panel" onSubmit={onSubmit}>
        {error && <div className="alert">{error}</div>}
        <div className="grid-2">
          <label className="field">
            <span>Файл</span>
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
            />
          </label>
          <label className="field">
            <span>Тип</span>
            <Select
              value={uploadType}
              onChange={setUploadType}
              options={[
                { value: "sales", label: "Продажи" },
                { value: "stocks", label: "Остатки" },
                { value: "both", label: "Продажи + Остатки" },
                { value: "promo_motivation", label: "Доп. мотивация" },
              ]}
            />
          </label>
          <label className="field">
            <span>Год</span>
            <input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>Месяц</span>
            <Select
              value={String(month)}
              onChange={(v) => setMonth(Number(v))}
              options={Array.from({ length: 12 }, (_, i) => ({
                value: String(i + 1),
                label: String(i + 1),
              }))}
            />
          </label>
          <label className="field">
            <span>Дата остатков</span>
            <DatePicker value={stockDate} onChange={setStockDate} placeholder="Необязательно" />
          </label>
        </div>
        <div style={{ marginTop: 16 }}>
          <button className="btn" type="submit" disabled={loading || !file}>
            {loading ? "Загружаем…" : "Загрузить"}
          </button>
        </div>
      </form>
      {result && (
        <div className="panel">
          <h2>Результат: {result.status}</h2>
          <p>
            Обработано строк: <strong>{result.processed_rows}</strong>
          </p>
          {!!result.errors?.length && (
            <>
              <button className="btn secondary" type="button" onClick={downloadErrors} style={{ marginBottom: 12 }}>
                Скачать ошибки.xlsx
              </button>
              <div className="alert-list">
                {result.errors.map((err, idx) => (
                  <div key={idx} className="alert">
                    Строка {err.row}: [{err.field}] {err.message}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
