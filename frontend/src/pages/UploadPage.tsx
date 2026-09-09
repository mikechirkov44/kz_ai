import { FormEvent, useEffect, useState } from "react";
import { api, downloadFile } from "../api";
import DataTable from "../components/DataTable";
import DatePicker from "../components/DatePicker";
import { ExcelLabel } from "../components/ExcelIcon";
import FilePicker from "../components/FilePicker";
import ManualUploadForm from "../components/ManualUploadForm";
import Pager from "../components/Pager";
import PageHeader from "../components/PageHeader";
import Select from "../components/Select";
import UploadErrorsModal from "../components/UploadErrorsModal";
import UploadFileModal, { type UploadFilePreview, type UploadFileTab } from "../components/UploadFileModal";
import { MONTH_OPTIONS, yearOptions } from "../months";
import { hasUploadErrors, type UploadErrorItem } from "../uploadErrors";

type UploadResult = {
  status: string;
  processed_rows: number;
  errors: UploadErrorItem[];
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
  seed: "Начальные данные",
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
  const [mode, setMode] = useState<"excel" | "manual">("manual");
  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [uploadType, setUploadType] = useState("sales");
  const [stockDate, setStockDate] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [errorsOpen, setErrorsOpen] = useState(false);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [viewRow, setViewRow] = useState<HistoryRow | null>(null);
  const [viewTab, setViewTab] = useState<UploadFileTab>("file");
  const [viewPreview, setViewPreview] = useState<UploadFilePreview | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState("");

  async function loadHistory(p = 1) {
    const data = await api<{ items: HistoryRow[]; total: number }>(
      `/api/v1/uploads?page=${p}&page_size=50`,
    );
    setHistory(data.items);
    setHistoryTotal(data.total);
    setPage(p);
  }

  useEffect(() => {
    loadHistory(1)
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить историю"))
      .finally(() => setHistoryLoading(false));
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
      setErrorsOpen(hasUploadErrors(json.errors));
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

  async function downloadOriginal(row: HistoryRow) {
    setError("");
    try {
      await downloadFile(`/api/v1/uploads/${row.id}/file`, row.file_name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось скачать файл");
    }
  }

  async function openHistory(row: HistoryRow, tab: UploadFileTab = "file") {
    setViewRow(row);
    setViewTab(tab);
    setViewPreview(null);
    setViewError("");
    setViewLoading(true);
    try {
      const data = await api<UploadFilePreview>(`/api/v1/uploads/${row.id}/preview`);
      setViewPreview(data);
    } catch (err) {
      setViewError(err instanceof Error ? err.message : "Не удалось открыть файл");
    } finally {
      setViewLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Ввод данных"
        subtitle="Продажи, остатки и мотивация"
      />
      <div className="seg-tabs" role="tablist" aria-label="Способ загрузки">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "manual"}
          className={`seg-tab ${mode === "manual" ? "active" : ""}`}
          onClick={() => setMode("manual")}
        >
          В сервисе
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "excel"}
          className={`seg-tab ${mode === "excel" ? "active" : ""}`}
          onClick={() => setMode("excel")}
        >
          Excel
        </button>
      </div>
      {mode === "manual" && (
        <ManualUploadForm
          onSuccess={(json) => {
            setResult(json);
            setPreview(null);
            setError("");
            void loadHistory(1);
          }}
        />
      )}
      {mode === "excel" && (
      <>
      <div className="panel">
        <h2>Шаблоны форм</h2>
        <div className="toolbar">
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("sales")}>
            <ExcelLabel>Шаблон продаж</ExcelLabel>
          </button>
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("stocks")}>
            <ExcelLabel>Шаблон остатков</ExcelLabel>
          </button>
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("both")}>
            <ExcelLabel>Шаблон продажи+остатки</ExcelLabel>
          </button>
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("promo_motivation")}>
            <ExcelLabel>Шаблон доп. мотивации</ExcelLabel>
          </button>
          <button type="button" className="btn secondary" onClick={() => downloadTemplate("quarterly_plans")}>
            <ExcelLabel>Шаблон квартальных планов</ExcelLabel>
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
            <Select value={String(year)} onChange={(v) => setYear(Number(v))} options={yearOptions()} />
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
      </>
      )}
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
          {hasUploadErrors(result.errors) && (
            <div className="toolbar" style={{ margin: "8px 0 0" }}>
              <button className="btn" type="button" onClick={() => setErrorsOpen(true)}>
                Показать ошибки
              </button>
            </div>
          )}
        </div>
      )}
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "14px 16px 0" }}>
          <h2 style={{ margin: 0 }}>История загрузок</h2>
        </div>
        <DataTable
          storageKey="upload-history"
          rows={history}
          rowKey={(r) => r.id}
          empty="Пока нет загрузок"
          loading={historyLoading}
          onRowClick={openHistory}
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
              title: "Источник",
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
                <div className="toolbar" style={{ margin: 0, gap: 6 }} onClick={(e) => e.stopPropagation()}>
                  {r.has_file && (
                    <button type="button" className="btn secondary sm" onClick={() => openHistory(r)}>
                      <ExcelLabel size={14}>Файл</ExcelLabel>
                    </button>
                  )}
                  {r.has_errors && (
                    <button type="button" className="btn secondary sm" onClick={() => openHistory(r, "errors")}>
                      Ошибки
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
      </div>
      <UploadErrorsModal
        open={errorsOpen && hasUploadErrors(result?.errors)}
        processedRows={result?.processed_rows || 0}
        errors={result?.errors || []}
        onClose={() => setErrorsOpen(false)}
      />
      <UploadFileModal
        open={Boolean(viewRow)}
        title={viewRow?.file_name || "Документ"}
        subtitle={
          viewRow
            ? `${TYPE_LABEL[viewRow.upload_type] || viewRow.upload_type} · ${STATUS_LABEL[viewRow.status] || viewRow.status}`
            : undefined
        }
        loading={viewLoading}
        error={viewError}
        preview={viewPreview}
        initialTab={viewTab}
        onClose={() => {
          setViewRow(null);
          setViewPreview(null);
          setViewError("");
          setViewTab("file");
        }}
        onDownloadFile={viewRow ? () => downloadOriginal(viewRow) : undefined}
      />
      <Pager
        page={page}
        total={historyTotal}
        disabled={historyLoading}
        onChange={(p) => void loadHistory(p).catch(() => undefined)}
      />
    </>
  );
}
