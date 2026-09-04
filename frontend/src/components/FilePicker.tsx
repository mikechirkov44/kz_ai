import { useRef } from "react";

type Props = {
  file: File | null;
  onChange: (file: File | null) => void;
  accept?: string;
};

export default function FilePicker({ file, onChange, accept = ".xlsx,.xls" }: Props) {
  const input = useRef<HTMLInputElement>(null);

  return (
    <div className="file-pick">
      <input
        ref={input}
        type="file"
        accept={accept}
        onChange={(e) => onChange(e.target.files?.[0] || null)}
      />
      <button type="button" className="btn secondary sm" onClick={() => input.current?.click()}>
        Выбрать файл
      </button>
      <span className={file ? "file-pick-name" : "muted"}>{file ? file.name : "Файл не выбран"}</span>
      {file && (
        <button
          type="button"
          className="file-pick-clear"
          onClick={() => {
            onChange(null);
            if (input.current) input.current.value = "";
          }}
          aria-label="Убрать файл"
        >
          ✕
        </button>
      )}
    </div>
  );
}
