import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import EmptyState from "./EmptyState";
import { useHorizontalOverflow } from "../useHorizontalOverflow";

export type DataTableColumn<T> = {
  key: string;
  title: string;
  width?: number;
  minWidth?: number;
  sortable?: boolean;
  sticky?: boolean;
  align?: "left" | "right" | "center";
  getValue?: (row: T) => string | number | boolean | null | undefined;
  render?: (row: T) => ReactNode;
};

export type EmptyAction = { to: string; label: string };

type Props<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  empty?: string;
  emptyHint?: string;
  emptyAction?: EmptyAction;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  maxHeight?: string | number;
  storageKey?: string;
};

type SortState = { key: string; dir: "asc" | "desc" } | null;

function colClassName<T>(col: DataTableColumn<T>, extra?: string): string | undefined {
  const parts = [
    col.sticky ? "sticky" : "",
    col.align === "right" ? "num" : "",
    col.align === "center" ? "center" : "",
    extra || "",
  ].filter(Boolean);
  return parts.length ? parts.join(" ") : undefined;
}

function compareValues(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0;
  if (a == null) return -1;
  if (b == null) return 1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "boolean" && typeof b === "boolean") return Number(a) - Number(b);
  return String(a).localeCompare(String(b), "ru", { numeric: true, sensitivity: "base" });
}

export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty = "Нет данных",
  emptyHint,
  emptyAction,
  loading = false,
  onRowClick,
  maxHeight = "calc(100vh - 260px)",
  storageKey,
}: Props<T>) {
  const [sort, setSort] = useState<SortState>(null);
  const [widths, setWidths] = useState<Record<string, number>>(() => {
    if (!storageKey) return {};
    try {
      const raw = localStorage.getItem(`table_widths:${storageKey}`);
      return raw ? (JSON.parse(raw) as Record<string, number>) : {};
    } catch {
      return {};
    }
  });
  const { ref: overflowRef, overflow } = useHorizontalOverflow([columns.length, rows.length, loading]);
  const dragRef = useRef<{ key: string; startX: number; startW: number } | null>(null);

  useEffect(() => {
    if (!storageKey) return;
    localStorage.setItem(`table_widths:${storageKey}`, JSON.stringify(widths));
  }, [widths, storageKey]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      const col = columns.find((c) => c.key === drag.key);
      const minW = col?.minWidth ?? 72;
      const next = Math.max(minW, drag.startW + (e.clientX - drag.startX));
      setWidths((prev) => ({ ...prev, [drag.key]: next }));
    };
    const onUp = () => {
      dragRef.current = null;
      document.body.classList.remove("col-resizing");
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [columns]);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const copy = [...rows];
    copy.sort((ra, rb) => {
      const va = col.getValue ? col.getValue(ra) : (ra as Record<string, unknown>)[col.key];
      const vb = col.getValue ? col.getValue(rb) : (rb as Record<string, unknown>)[col.key];
      const cmp = compareValues(va, vb);
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [rows, sort, columns]);

  function toggleSort(key: string, enabled?: boolean) {
    if (enabled === false) return;
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: "asc" };
      if (prev.dir === "asc") return { key, dir: "desc" };
      return null;
    });
  }

  function startResize(key: string, e: ReactMouseEvent, currentWidth: number) {
    e.preventDefault();
    e.stopPropagation();
    dragRef.current = { key, startX: e.clientX, startW: currentWidth };
    document.body.classList.add("col-resizing");
  }

  return (
    <div>
      {overflow && !loading && !!rows.length && (
        <p className="wide-table-hint">Листайте таблицу вправо →</p>
      )}
      <div className={`table-wrap${overflow ? " is-wide" : ""}`} ref={overflowRef} style={{ maxHeight }}>
      <table className="data-table">
        <colgroup>
          {columns.map((col) => {
            const w = widths[col.key] ?? col.width;
            return <col key={col.key} style={w ? { width: w } : undefined} />;
          })}
        </colgroup>
        <thead>
          <tr>
            {columns.map((col) => {
              const w = widths[col.key] ?? col.width ?? 140;
              const sortable = col.sortable !== false;
              const active = sort?.key === col.key;
              return (
                <th
                  key={col.key}
                  className={colClassName(col, sortable ? "sortable" : "")}
                  style={{
                    width: widths[col.key] ?? col.width,
                    minWidth: col.minWidth ?? 72,
                  }}
                  onClick={() => toggleSort(col.key, sortable)}
                >
                  <span className="th-label">
                    {col.title}
                    {sortable && (
                      <span className={`sort-ind ${active ? "on" : ""}`}>
                        {active ? (sort?.dir === "asc" ? "↑" : "↓") : "↕"}
                      </span>
                    )}
                  </span>
                  <span
                    className="col-resizer"
                    onMouseDown={(e) => startResize(col.key, e, w)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }).map((_, idx) => (
                <tr key={`skel-${idx}`} className="table-skeleton-row">
                  {columns.map((col) => (
                    <td key={col.key} className={colClassName(col)}>
                      <span className="skel" />
                    </td>
                  ))}
                </tr>
              ))
            : sortedRows.map((row, idx) => (
            <tr
              key={rowKey(row, idx)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              style={onRowClick ? { cursor: "pointer" } : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className={colClassName(col)}>
                  {col.render
                    ? col.render(row)
                    : String(
                        (col.getValue
                          ? col.getValue(row)
                          : (row as Record<string, unknown>)[col.key]) ?? "—",
                      )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!loading && !rows.length && (
        <EmptyState title={empty} hint={emptyHint} action={emptyAction} />
      )}
      </div>
    </div>
  );
}
