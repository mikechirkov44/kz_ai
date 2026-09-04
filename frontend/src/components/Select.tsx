import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type SelectOption = { value: string; label: string };

type Props = {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  search?: string;
  onSearch?: (value: string) => void;
  searchPlaceholder?: string;
};

type MenuPos = { top: number; left: number; width: number; maxHeight: number };

export default function Select({
  value,
  options,
  onChange,
  placeholder = "Выберите",
  search,
  onSearch,
  searchPlaceholder = "Поиск",
}: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<MenuPos | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value);

  function place() {
    const el = trigger.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const gap = 4;
    const wanted = 260;
    const below = window.innerHeight - r.bottom - gap - 8;
    const above = r.top - gap - 8;
    const openUp = below < 160 && above > below;
    const maxHeight = Math.max(120, Math.min(wanted, openUp ? above : below));
    setPos({
      top: openUp ? r.top - gap - maxHeight : r.bottom + gap,
      left: r.left,
      width: r.width,
      maxHeight,
    });
  }

  useLayoutEffect(() => {
    if (!open) {
      setPos(null);
      return;
    }
    place();
    const onWin = () => place();
    window.addEventListener("resize", onWin);
    window.addEventListener("scroll", onWin, true);
    return () => {
      window.removeEventListener("resize", onWin);
      window.removeEventListener("scroll", onWin, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (root.current?.contains(t) || menu.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  function pick(next: string) {
    onChange(next);
    setOpen(false);
  }

  return (
    <div className="ui-select" ref={root}>
      <button
        ref={trigger}
        type="button"
        className="ui-select-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span>{selected?.label || placeholder}</span>
        <span className="chev">▾</span>
      </button>
      {open &&
        pos &&
        createPortal(
          <div
            ref={menu}
            className="ui-select-menu"
            role="listbox"
            style={{
              top: pos.top,
              left: pos.left,
              width: pos.width,
              maxHeight: pos.maxHeight,
            }}
          >
            {onSearch && (
              <div className="ui-select-search-wrap">
                <input
                  className="ui-select-search"
                  value={search || ""}
                  placeholder={searchPlaceholder}
                  autoFocus
                  autoComplete="off"
                  onChange={(e) => onSearch(e.target.value)}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={(e) => e.stopPropagation()}
                />
              </div>
            )}
            <div className="ui-select-options">
              {options.length === 0 && (
                <div className="ui-select-option ui-select-empty">Ничего не найдено</div>
              )}
              {options.map((o) => (
                <div
                  key={o.value || "__empty"}
                  className={`ui-select-option ${o.value === value ? "active" : ""}`}
                  role="option"
                  aria-selected={o.value === value}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    pick(o.value);
                  }}
                >
                  {o.label}
                </div>
              ))}
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
