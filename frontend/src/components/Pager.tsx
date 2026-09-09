import { lastPage, pageRangeLabel } from "../pageRange";

type Props = {
  page: number;
  total: number;
  pageSize?: number;
  disabled?: boolean;
  onChange: (page: number) => void;
};

export default function Pager({ page, total, pageSize = 50, disabled = false, onChange }: Props) {
  if (total <= 0) return null;
  const last = lastPage(total, pageSize);
  return (
    <div className="toolbar">
      <button
        type="button"
        className="btn secondary"
        disabled={disabled || page <= 1}
        onClick={() => onChange(page - 1)}
      >
        ←
      </button>
      <span className="pill">{pageRangeLabel(page, total, pageSize)}</span>
      <button
        type="button"
        className="btn secondary"
        disabled={disabled || page >= last}
        onClick={() => onChange(page + 1)}
      >
        →
      </button>
    </div>
  );
}
