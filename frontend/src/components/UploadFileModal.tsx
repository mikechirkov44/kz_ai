import { useEffect, useState } from "react";
import EmptyState from "./EmptyState";
import { ExcelLabel } from "./ExcelIcon";
import Modal from "./Modal";
import type { UploadErrorItem } from "../uploadErrors";

export type UploadFilePreview = {
  file_name: string;
  upload_type: string;
  status: string;
  has_file: boolean;
  has_errors: boolean;
  errors?: UploadErrorItem[];
  columns: string[];
  rows: Record<string, string | number | null>[];
  total_rows: number;
  shown_rows: number;
};

export type UploadFileTab = "file" | "errors";

type Props = {
  open: boolean;
  title: string;
  subtitle?: string;
  loading?: boolean;
  error?: string;
  preview: UploadFilePreview | null;
  initialTab?: UploadFileTab;
  onClose: () => void;
  onDownloadFile?: () => void;
};

function cellText(value: string | number | null | undefined): string {
  if (value == null || value === "") return "";
  return String(value);
}

export default function UploadFileModal({
  open,
  title,
  subtitle,
  loading = false,
  error = "",
  preview,
  initialTab = "file",
  onClose,
  onDownloadFile,
}: Props) {
  const [tab, setTab] = useState<UploadFileTab>(initialTab);
  const columns = preview?.columns || [];
  const rows = preview?.rows || [];
  const errors = preview?.errors || [];
  const missingFile = Boolean(preview && !preview.has_file);
  const showErrorsTab = Boolean(preview?.has_errors || errors.length);

  useEffect(() => {
    if (open) setTab(initialTab);
  }, [open, initialTab]);

  return (
    <Modal open={open} wide title={title} subtitle={subtitle} onClose={onClose}>
      {preview?.has_file && onDownloadFile ? (
        <div className="toolbar" style={{ margin: "0 0 12px" }}>
          <button type="button" className="btn secondary sm" onClick={onDownloadFile}>
            <ExcelLabel size={14}>Скачать файл</ExcelLabel>
          </button>
        </div>
      ) : null}
      {showErrorsTab ? (
        <div className="seg-tabs" role="tablist" aria-label="Просмотр загрузки" style={{ marginBottom: 12 }}>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "file"}
            className={`seg-tab ${tab === "file" ? "active" : ""}`}
            onClick={() => setTab("file")}
          >
            Документ
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "errors"}
            className={`seg-tab ${tab === "errors" ? "active" : ""}`}
            onClick={() => setTab("errors")}
          >
            Ошибки ({errors.length})
          </button>
        </div>
      ) : null}
      {error ? <div className="alert">{error}</div> : null}
      {loading ? (
        <p className="muted">Открываем файл…</p>
      ) : tab === "errors" ? (
        <div className="table-wrap upload-file-preview upload-errors-table">
          <table>
            <thead>
              <tr>
                <th>Строка</th>
                <th>Поле</th>
                <th>Ошибка</th>
              </tr>
            </thead>
            <tbody>
              {!errors.length ? (
                <tr>
                  <td colSpan={3}>Ошибок нет</td>
                </tr>
              ) : (
                errors.map((err, idx) => (
                  <tr key={`${err.row}-${err.field}-${idx}`}>
                    <td className="num">{err.row}</td>
                    <td>{err.field}</td>
                    <td>{err.message}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : missingFile ? (
        <EmptyState
          title="Файл не сохранён"
          hint="У seed-загрузок и ввода в сервисе исходного Excel на диске нет."
        />
      ) : preview ? (
        <>
          <p className="muted" style={{ margin: "0 0 8px" }}>
            {preview.shown_rows === preview.total_rows
              ? `Строк: ${preview.total_rows}`
              : `Показаны ${preview.shown_rows} из ${preview.total_rows} строк`}
          </p>
          <div className="table-wrap upload-file-preview">
            <table>
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!rows.length ? (
                  <tr>
                    <td colSpan={Math.max(columns.length, 1)}>В файле нет строк</td>
                  </tr>
                ) : (
                  rows.map((row, idx) => (
                    <tr key={idx}>
                      {columns.map((col) => (
                        <td key={col}>{cellText(row[col])}</td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </Modal>
  );
}
