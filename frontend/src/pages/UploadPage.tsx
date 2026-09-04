import { FormEvent, useEffect, useState } from "react";
import { api, downloadFile } from "../api";
import DataTable from "../components/DataTable";
import DatePicker from "../components/DatePicker";
import FilePicker from "../components/FilePicker";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";
import { MONTH_OPTIONS } from "../months";

type UploadResult = {
  status: string;
  processed_rows: number;
  errors: { row: number; field: string; message: string }[];
  upload_id: string;
};

type PreviewResult = {
  status: string;
  total_rows: number;
  valid_rows: number;
  error_count: number;
  errors: { row: number; field: string; message: string }[];
  sample_rows: {
    row: number;
    counterparty: string;
    article: string;
    shop?: string;
    quantity: number;
    price?: number | null;
  }[];
};

type HistoryRow = {
  id: string;
  file_name: string;
  upload_type: string;
  status: string;
  processed_rows: number;
  error_count: number;
  period_year?: number | null;
  period_month?: number | null;
  stock_date?: string | null;
  created_at: string;
  user_email?: string | null;
  has_file: boolean;
  has_errors: boolean;
};

const TYPE_LABEL: Record<string, string> = {
  sales: "Продажи",
  stocks: "Остатки",
  both: "Продажи + остатки",
  promo_motivation: "Доп. мотивация",
  quarterly_plans: "Квартальные планы",
};

const STATUS_LABEL: Record<string, string> = {
  success: "Успех",
  partial: "Частично",
  error: "Ошибки",
};

function statusClass(status: string): string {
  if (status === "success") return "pill ok";
  if (status === "partial") return "pill warn";
  return "pill bad";
}

function periodLabel(row: HistoryRow): string {
  if (row.period_year && row.period_month) {
    return `${row.period_year}-${String(row.period_month).padStart(2, "0")}`;
  }
  return row.stock_date || "—";
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [uploadType, setUploadType] = useState("sales");
  const [stockDate, setStockDate] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [page, setPage] = useState(1);

  async function loadHistory(p = 1) {
    const data = await api<{ items: HistoryRow[]; total: number }>(
      `/api/v1/uploads?page=${p}&page_size=50`,
    );
    setHistory(data.items);
    setHistoryTotal(data.total);
    setPage(p);
  }

  useEffect(() => {
    loadHistory(1).catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить историю"));
  }, []);

  async function onPreview() {
    if (!file) return;
    setError("");
    setLoading(true);
    setPreview(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const json = await api<PreviewResult>("/api/v1/uploads/preview", { method: "POST", body });
      setPreview(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка предпросмотра");
    } finally {
      setLoading(false);
    }
  }

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
          : uploadType === "quarterly_plans"
            ? "/api/v1/uploads/quarterly-plans"
            : "/api/v1/uploads/sales";
      const json = await api<UploadResult>(path, { method: "POST", body });
      setResult(json);
      setPreview(null);
      await loadHistory(1);
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

  async function downloadErrors(uploadId: string) {
    setError("");
    try {
      await downloadFile(`/api/v1/uploads/${uploadId}/errors.xlsx`, `errors_${uploadId}.xlsx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось скачать ошибки");
    }
  }

  async function downloadOriginal(row: HistoryRow) {
    setError("");
    try {
      await downloadFile(`/api/v1/uploads/${row.id}/file`, row.file_name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось скачать файл");
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
        <p className="muted">Колонки: Головной контрагент, Артикул, Магазин, Количество, Цена продажи</p>
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
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("quarterly_plans")}>
            Шаблон квартальных планов
          </button>
        </div>
      </div>
      <form className="panel upload-form" onSubmit={onSubmit}>
        {error && <div className="alert">{error}</div>}
        <label className="field">
          <span>Файл</span>
          <FilePicker file={file} onChange={setFile} />
        </label>
        <div className="grid-4">
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
                { value: "quarterly_plans", label: "Квартальные планы" },
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
              options={MONTH_OPTIONS}
            />
          </label>
          <label className="field">
            <span>Дата остатков</span>
            <DatePicker value={stockDate} onChange={setStockDate} placeholder="Необязательно" />
          </label>
        </div>
        <div className="upload-form-actions">
          <button
            className="btn secondary"
            type="button"
            disabled={loading || !file || uploadType === "quarterly_plans"}
            onClick={onPreview}
          >
            Предпросмотр
          </button>
          <button className="btn" type="submit" disabled={loading || !file}>
            {loading ? "Загружаем…" : "Загрузить"}
          </button>
        </div>
      </form>
      {preview && (
        <div className="panel">
          <h2>Предпросмотр: {STATUS_LABEL[preview.status] || preview.status}</h2>
          <p>
            Строк в файле: <strong>{preview.total_rows}</strong>, валидных:{" "}
            <strong>{preview.valid_rows}</strong>, ошибок: <strong>{preview.error_count}</strong>
          </p>
          {!!preview.sample_rows?.length && (
            <div className="table-wrap" style={{ marginBottom: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th>Строка</th>
                    <th>Контрагент</th>
                    <th>Артикул</th>
                    <th>Магазин</th>
                    <th>Кол-во</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.sample_rows.map((r) => (
                    <tr key={r.row}>
                      <td>{r.row}</td>
                      <td>{r.counterparty}</td>
                      <td>{r.article}</td>
                      <td>{r.shop || "—"}</td>
                      <td>{r.quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!!preview.errors?.length && (
            <div className="alert-list">
              {preview.errors.slice(0, 30).map((err, idx) => (
                <div key={idx} className="alert">
                  Строка {err.row}: [{err.field}] {err.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {result && (
        <div className="panel">
          <h2>Результат: {STATUS_LABEL[result.status] || result.status}</h2>
          <p>
            Обработано строк: <strong>{result.processed_rows}</strong>
          </p>
          {!!result.errors?.length && (
            <>
              <button className="btn secondary" type="button" onClick={() => downloadErrors(result.upload_id)} style={{ marginBottom: 12 }}>
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
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "14px 16px 0" }}>
          <h2 style={{ margin: 0 }}>История загрузок</h2>
          <p className="muted">Всего: {historyTotal}</p>
        </div>
        <DataTable
          storageKey="upload-history"
          rows={history}
          rowKey={(r) => r.id}
          empty="Пока нет загрузок"
          columns={[
            {
              key: "created_at",
              title: "Когда",
              width: 170,
              getValue: (r) => r.created_at,
              render: (r) => (r.created_at ? new Date(r.created_at).toLocaleString("ru-RU") : "—"),
            },
            {
              key: "file_name",
              title: "Файл",
              width: 220,
              sticky: true,
              getValue: (r) => r.file_name,
            },
            {
              key: "upload_type",
              title: "Тип",
              width: 150,
              getValue: (r) => TYPE_LABEL[r.upload_type] || r.upload_type,
            },
            {
              key: "period",
              title: "Период",
              width: 110,
              getValue: periodLabel,
            },
            {
              key: "status",
              title: "Статус",
              width: 120,
              getValue: (r) => r.status,
              render: (r) => <span className={statusClass(r.status)}>{STATUS_LABEL[r.status] || r.status}</span>,
            },
            {
              key: "processed_rows",
              title: "Строк",
              width: 90,
              align: "right",
            },
            {
              key: "user_email",
              title: "Кто",
              width: 180,
              getValue: (r) => r.user_email || "",
              render: (r) => r.user_email || "—",
            },
            {
              key: "actions",
              title: "",
              width: 220,
              sortable: false,
              render: (r) => (
                <div className="toolbar" style={{ margin: 0, gap: 6 }}>
                  {r.has_file && (
                    <button type="button" className="btn secondary sm" onClick={() => downloadOriginal(r)}>
                      Файл
                    </button>
                  )}
                  {r.has_errors && (
                    <button type="button" className="btn secondary sm" onClick={() => downloadErrors(r.id)}>
                      Ошибки
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
      </div>
      <div className="toolbar">
        <button className="btn secondary" disabled={page <= 1} onClick={() => loadHistory(page - 1).catch(() => undefined)}>
          ←
        </button>
        <span className="pill">стр. {page}</span>
        <button
          className="btn secondary"
          disabled={history.length < 50}
          onClick={() => loadHistory(page + 1).catch(() => undefined)}
        >
          →
        </button>
      </div>
    </>
  );
}
