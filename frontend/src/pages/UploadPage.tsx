import { FormEvent, useEffect, useState } from "react";
import { api, downloadFile } from "../api";
import Checkbox from "../components/Checkbox";
import DataTable from "../components/DataTable";
import RowActionsMenu from "../components/RowActionsMenu";
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
import { needsPeriod, needsStockDate } from "../manualUpload";
import { uploadDeleteConfirm } from "../uploadActions";
import { uploadPeriodLabel } from "../uploadPeriod";
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
  return uploadPeriodLabel(row);
}

export default function UploadPage() {
  const [mode, setMode] = useState<"excel" | "manual">("manual");
  const [files, setFiles] = useState<File[]>([]);
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
  const [selected, setSelected] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);

  async function loadHistory(p = 1) {
    const data = await api<{ items: HistoryRow[]; total: number }>(
      `/api/v1/uploads?page=${p}&page_size=50`,
    );
    setHistory(data.items);
    setHistoryTotal(data.total);
    setPage(p);
    const visible = new Set(data.items.map((row) => row.id));
    setSelected((prev) => prev.filter((id) => visible.has(id)));
  }

  useEffect(() => {
    loadHistory(1)
      .catch((err) => setError(err instanceof Error ? err.message : "Не удалось загрузить историю"))
      .finally(() => setHistoryLoading(false));
  }, []);

  function appendFiles(body: FormData) {
    for (const item of files) body.append("files", item);
  }

  async function onPreview() {
    if (!files.length) return;
    setError("");
    setLoading(true);
    setPreview(null);
    const body = new FormData();
    appendFiles(body);
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
    if (!files.length) return;
    setError("");
    setLoading(true);
    const body = new FormData();
    appendFiles(body);
    body.append("upload_type", uploadType);
    if (needsPeriod(uploadType)) {
      body.append("period_year", String(year));
      body.append("period_month", String(month));
    }
    if (needsStockDate(uploadType) && !stockDate) {
      setError("Для остатков укажите дату");
      setLoading(false);
      return;
    }
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

  async function removeUploads(rows: HistoryRow[]) {
    if (!rows.length || !window.confirm(uploadDeleteConfirm(rows))) return;
    setError("");
    setDeleting(true);
    try {
      for (const row of rows) {
        await api(`/api/v1/uploads/${row.id}`, { method: "DELETE" });
      }
      if (rows.some((row) => row.id === viewRow?.id)) setViewRow(null);
      setSelected((prev) => prev.filter((id) => !rows.some((row) => row.id === id)));
      await loadHistory(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить загрузку");
      await loadHistory(page);
    } finally {
      setDeleting(false);
    }
  }

  function toggleSelected(id: string, on: boolean) {
    setSelected((prev) => (on ? [...prev, id] : prev.filter((item) => item !== id)));
  }

  const selectedRows = history.filter((row) => selected.includes(row.id));
  const allChecked = history.length > 0 && history.every((row) => selected.includes(row.id));

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
          <FilePicker files={files} onFilesChange={setFiles} multiple />
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
          {needsPeriod(uploadType) && (
            <>
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
            </>
          )}
          {(needsStockDate(uploadType) || uploadType === "promo_motivation") && (
            <label className="field">
              <span>Дата остатков</span>
              <DatePicker
                value={stockDate}
                onChange={setStockDate}
                placeholder={needsStockDate(uploadType) ? "Выберите дату" : "Необязательно"}
              />
            </label>
          )}
        </div>
        <div className="upload-form-actions">
          <button
            className="btn secondary"
            type="button"
            disabled={loading || !files.length || uploadType === "quarterly_plans"}
            onClick={onPreview}
          >
            Предпросмотр
          </button>
          <button className="btn" type="submit" disabled={loading || !files.length}>
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
      <div className="panel" style={{ padding: 0 }}>
        <div className="upload-history-head">
          <h2>История загрузок</h2>
          {selectedRows.length > 0 ? (
            <button
              type="button"
              className="btn danger sm"
              disabled={deleting}
              onClick={() => void removeUploads(selectedRows)}
            >
              {allChecked ? "Удалить все" : `Удалить выбранные (${selectedRows.length})`}
            </button>
          ) : null}
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
              key: "select",
              title: (
                <Checkbox
                  checked={allChecked}
                  disabled={!history.length || deleting}
                  aria-label="Выделить все"
                  onClick={(event) => event.stopPropagation()}
                  onChange={(on) => setSelected(on ? history.map((row) => row.id) : [])}
                />
              ),
              width: 44,
              minWidth: 44,
              sortable: false,
              align: "center",
              render: (r) => (
                <Checkbox
                  checked={selected.includes(r.id)}
                  disabled={deleting}
                  aria-label={`Выбрать ${r.file_name}`}
                  onClick={(event) => event.stopPropagation()}
                  onChange={(on) => toggleSelected(r.id, on)}
                />
              ),
            },
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
              width: 56,
              minWidth: 56,
              sortable: false,
              align: "center",
              render: (r) => (
                <RowActionsMenu
                  items={[
                    ...(r.has_file ? [{ id: "file", label: "Файл", onSelect: () => openHistory(r) }] : []),
                    ...(r.has_errors
                      ? [{ id: "errors", label: "Ошибки", onSelect: () => openHistory(r, "errors") }]
                      : []),
                    { id: "delete", label: "Удалить", danger: true, onSelect: () => void removeUploads([r]) },
                  ]}
                />
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
