import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type RowAction = {
  id: string;
  label: string;
  danger?: boolean;
  onSelect: () => void;
};

type Props = {
  items: RowAction[];
};

export default function RowActionsMenu({ items }: Props) {
  const [open, setOpen] = useState(false);
  const [place, setPlace] = useState({ top: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointer(event: MouseEvent) {
      const target = event.target as Node;
      if (buttonRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function toggle() {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (rect) {
      const width = 180;
      const height = 8 + items.length * 36;
      const below = rect.bottom + 6;
      const top = below + height > window.innerHeight ? Math.max(8, rect.top - height - 6) : below;
      setPlace({ top, left: Math.max(8, rect.right - width) });
    }
    setOpen((current) => !current);
  }

  return (
    <div className="row-actions" onClick={(event) => event.stopPropagation()}>
      <button
        ref={buttonRef}
        type="button"
        className="btn ghost sm row-actions-btn"
        aria-label="Действия"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={toggle}
      >
        ···
      </button>
      {open
        ? createPortal(
            <div ref={menuRef} className="row-actions-menu" role="menu" style={{ top: place.top, left: place.left }}>
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="menuitem"
                  className={item.danger ? "is-danger" : undefined}
                  onClick={() => {
                    setOpen(false);
                    item.onSelect();
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
