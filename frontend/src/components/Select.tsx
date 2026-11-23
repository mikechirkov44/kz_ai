import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";

export type SelectOption = { value: string; label: string };

type BaseProps = {
  options: SelectOption[];
  placeholder?: string;
  search?: string;
  onSearch?: (value: string) => void;
  searchPlaceholder?: string;
  allowCreate?: boolean;
};

type SingleProps = BaseProps & {
  multiple?: false;
  value: string;
  onChange: (value: string) => void;
};

type MultiProps = BaseProps & {
  multiple: true;
  value: string[];
  onChange: (value: string[]) => void;
};

type Props = SingleProps | MultiProps;

type MenuPos = { top: number; left: number; width: number; maxHeight: number };

function selectedValues(value: string | string[]): string[] {
  return Array.isArray(value) ? value.filter(Boolean) : [value];
}

export default function Select(props: Props) {
  const {
    options,
    placeholder = "Выберите",
    search,
    onSearch,
    searchPlaceholder = "Поиск",
    allowCreate = false,
  } = props;
  const multiple = props.multiple === true;
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<MenuPos | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const keyboardDirection = useRef(0);
  const typed = (search || "").trim();
  const hasTypedOption = options.some(
    (o) => o.value.toLowerCase() === typed.toLowerCase() || o.label.toLowerCase() === typed.toLowerCase(),
  );
  const menuOptions =
    allowCreate && typed && !hasTypedOption
      ? [{ value: typed, label: `Ввести «${typed}»` }, ...options]
      : options;
  const picked = selectedValues(props.value);
  const selected =
    picked.length === 1
      ? options.find((o) => o.value === picked[0]) || { value: picked[0], label: picked[0] }
      : undefined;

  function triggerLabel(): string {
    if (!picked.length) return placeholder;
    if (picked.length === 1) return selected?.label || placeholder;
    return `${picked.length} выбрано`;
  }

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
    if (!multiple) {
      (props as SingleProps).onChange(next);
      setOpen(false);
      trigger.current?.focus();
      return;
    }
    if (!next) {
      (props as MultiProps).onChange([]);
      setOpen(false);
      return;
    }
    const nextValues = picked.includes(next) ? picked.filter((id) => id !== next) : [...picked, next];
    (props as MultiProps).onChange(nextValues);
  }

  useLayoutEffect(() => {
    if (!pos || !keyboardDirection.current) return;
    const options = menu.current?.querySelectorAll<HTMLElement>('[role="option"]');
    if (options?.length) {
      const selected = menu.current?.querySelector<HTMLElement>('[aria-selected="true"]');
      (selected ?? options[keyboardDirection.current > 0 ? 0 : options.length - 1]).focus();
    }
    keyboardDirection.current = 0;
  }, [pos]);

  function handleMenuKey(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      trigger.current?.focus();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const options = Array.from(menu.current?.querySelectorAll<HTMLElement>('[role="option"]') ?? []);
      const index = options.indexOf(document.activeElement as HTMLElement);
      const next = event.key === "ArrowDown" ? Math.min(index + 1, options.length - 1)
        : index < 0 ? options.length - 1 : Math.max(index - 1, 0);
      options[next]?.focus();
    }
  }

  return (
    <div className="ui-select" ref={root}>
      <button
        ref={trigger}
        type="button"
        className="ui-select-trigger"
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(event) => {
          if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
            event.preventDefault();
            keyboardDirection.current = event.key === "ArrowDown" ? 1 : -1;
            setOpen(true);
          } else if (open) {
            handleMenuKey(event);
          }
        }}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-multiselectable={multiple || undefined}
      >
        <span>{triggerLabel()}</span>
        <span className="chev">▾</span>
      </button>
      {open &&
        pos &&
        createPortal(
          <div
            ref={menu}
            className="ui-select-menu"
            role="listbox"
            onKeyDown={handleMenuKey}
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
              {menuOptions.length === 0 && (
                <div className="ui-select-option ui-select-empty">Ничего не найдено</div>
              )}
              {menuOptions.map((o) => {
                const active = picked.includes(o.value) || (o.value === "" && picked.length === 0);
                return (
                  <div
                    key={o.value || "__empty"}
                    className={`ui-select-option ${active ? "active" : ""}`}
                    role="option"
                    tabIndex={-1}
                    aria-selected={active}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        pick(o.value);
                      }
                    }}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      pick(o.value);
                    }}
                  >
                    {multiple ? <span className="ui-select-check">{active ? "✓" : ""}</span> : null}
                    <span>{o.label}</span>
                    {!multiple && active && <span className="ui-select-check ui-select-check-end" aria-hidden="true">✓</span>}
                  </div>
                );
              })}
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
