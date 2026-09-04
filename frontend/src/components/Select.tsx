import { useEffect, useRef, useState } from "react";

export type SelectOption = { value: string; label: string };

type Props = {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
};

export default function Select({ value, options, onChange, placeholder = "Выберите" }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="ui-select" ref={root}>
      <button
        type="button"
        className="ui-select-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>{selected?.label || placeholder}</span>
        <span className="chev">▾</span>
      </button>
      {open && (
        <div className="ui-select-menu" role="listbox">
          {options.map((o) => (
            <div
              key={o.value}
              className={`ui-select-option ${o.value === value ? "active" : ""}`}
              role="option"
              aria-selected={o.value === value}
              onClick={() => {
                onChange(o.value);
                setOpen(false);
              }}
            >
              {o.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
