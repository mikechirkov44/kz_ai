import { useRef } from "react";

type Props = {
  file?: File | null;
  files?: File[];
  onChange?: (file: File | null) => void;
  onFilesChange?: (files: File[]) => void;
  multiple?: boolean;
  accept?: string;
};

export default function FilePicker({
  file = null,
  files,
  onChange,
  onFilesChange,
  multiple = false,
  accept = ".xlsx,.xls",
}: Props) {
  const input = useRef<HTMLInputElement>(null);
  const selected = files ?? (file ? [file] : []);

  function apply(next: File[]) {
    onFilesChange?.(next);
    onChange?.(next[0] || null);
  }

  function label(): string {
    if (!selected.length) return multiple ? "Файлы не выбраны" : "Файл не выбран";
    if (selected.length === 1) return selected[0].name;
    return selected.map((item) => item.name).join(", ");
  }

  return (
    <div className="file-pick">
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={(e) => apply(Array.from(e.target.files || []))}
      />
      <button type="button" className="btn secondary sm" onClick={() => input.current?.click()}>
        {multiple ? "Выбрать файлы" : "Выбрать файл"}
      </button>
      <span className={selected.length ? "file-pick-name" : "muted"} title={label()}>
        {label()}
      </span>
      {!!selected.length && (
        <button
          type="button"
          className="file-pick-clear"
          onClick={() => {
            apply([]);
            if (input.current) input.current.value = "";
          }}
          aria-label={multiple ? "Убрать файлы" : "Убрать файл"}
        >
          ✕
        </button>
      )}
    </div>
  );
}
