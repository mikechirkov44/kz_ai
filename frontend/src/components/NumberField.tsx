import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { appendDigit, digitFromKey, stepNumber } from "../numberField";

type Props = {
  value: string;
  onChange: (value: string) => void;
  min?: number;
  step?: number;
  placeholder?: string;
  integer?: boolean;
};

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "0", "⌫"] as const;

export default function NumberField({
  value,
  onChange,
  min = 0,
  step = 1,
  placeholder = "0",
  integer = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 220 });
  const root = useRef<HTMLDivElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const keys = integer ? KEYS.filter((key) => key !== ".") : KEYS;
  const valueRef = useRef(value);
  valueRef.current = value;

  useLayoutEffect(() => {
    if (!open) return;
    function place() {
      const el = root.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const width = Math.max(220, r.width);
      let top = r.bottom + 4;
      if (top + 260 > window.innerHeight - 8) top = Math.max(8, r.top - 264);
      let left = r.left;
      if (left + width > window.innerWidth - 8) left = Math.max(8, window.innerWidth - width - 8);
      setPos({ top, left, width });
    }
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (root.current?.contains(t) || pop.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "Escape" || e.key === "Enter") {
        e.preventDefault();
        setOpen(false);
        return;
      }
      const digit = digitFromKey(e.key, integer);
      if (!digit) return;
      e.preventDefault();
      onChange(appendDigit(valueRef.current, digit, integer));
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, integer, onChange]);

  return (
    <div className="ui-number" ref={root}>
      <button
        type="button"
        className="ui-number-step"
        onClick={() => onChange(stepNumber(value, -step, { min, integer }))}
        aria-label="Меньше"
      >
        −
      </button>
      <button type="button" className="ui-number-value" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className={value ? "" : "muted"}>{value || placeholder}</span>
      </button>
      <button
        type="button"
        className="ui-number-step"
        onClick={() => onChange(stepNumber(value, step, { min, integer }))}
        aria-label="Больше"
      >
        +
      </button>
      {open &&
        createPortal(
          <div className="ui-keypad" ref={pop} style={{ top: pos.top, left: pos.left, width: pos.width }}>
            <div className="ui-keypad-grid">
              {keys.map((key) => (
                <button
                  key={key}
                  type="button"
                  className="ui-keypad-key"
                  onClick={() => onChange(appendDigit(value, key, integer))}
                >
                  {key}
                </button>
              ))}
            </div>
            <button type="button" className="btn sm" onClick={() => setOpen(false)}>
              Готово
            </button>
          </div>,
          document.body,
        )}
    </div>
  );
}
