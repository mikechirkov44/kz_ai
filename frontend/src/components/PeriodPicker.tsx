import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  MONTH_OPTIONS,
  PeriodMode,
  defaultPeriodForMode,
  formatRuDate,
  monthClickPeriod,
  parseIsoDate,
  parseRuDate,
  snapPeriod,
  standardPeriodOptions,
  ymIndex,
} from "../months";

type Props = {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
  mode?: PeriodMode;
  minYear?: number;
  maxYear?: number;
};

const MONTHS_SHORT = ["Янв", "Фев", "Март", "Апр", "Май", "Июнь", "Июль", "Авг", "Сент", "Окт", "Нояб", "Дек"];

const HINT: Record<PeriodMode, string> = {
  range: "Выберите месяц начала и месяц окончания",
  "month-range": "Выберите месяц начала и месяц окончания",
  month: "Выберите месяц",
  quarter: "Выберите квартал",
};

function currentYear(): number {
  return new Date().getFullYear();
}

function CalendarIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M16 3v4M8 3v4M3 11h18" />
    </svg>
  );
}

export default function PeriodPicker({
  from,
  to,
  onChange,
  mode = "range",
  minYear = 2023,
  maxYear = currentYear(),
}: Props) {
  const [open, setOpen] = useState(false);
  const [draftFrom, setDraftFrom] = useState(from);
  const [draftTo, setDraftTo] = useState(to);
  const [fromText, setFromText] = useState(formatRuDate(from));
  const [toText, setToText] = useState(formatRuDate(to));
  const [pickingEnd, setPickingEnd] = useState(false);
  const [showPresets, setShowPresets] = useState(false);
  const [windowStart, setWindowStart] = useState(() => Math.max(minYear, (parseIsoDate(from)?.year || currentYear()) - 1));
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);

  function syncDraft(nextFrom: string, nextTo: string, nextPicking = false) {
    const snapped = snapPeriod(nextFrom, nextTo, mode);
    setDraftFrom(snapped.from);
    setDraftTo(snapped.to);
    setFromText(formatRuDate(snapped.from));
    setToText(formatRuDate(snapped.to));
    setPickingEnd(nextPicking);
  }

  function openPanel() {
    syncDraft(from, to);
    const y = parseIsoDate(from)?.year || currentYear();
    setWindowStart(Math.max(minYear, y - 1));
    setShowPresets(false);
    setOpen(true);
  }

  function closePanel() {
    setOpen(false);
    setPickingEnd(false);
    setShowPresets(false);
  }

  function apply() {
    const snapped = snapPeriod(draftFrom, draftTo, mode);
    onChange(snapped.from, snapped.to);
    closePanel();
  }

  function clearDraft() {
    const next = defaultPeriodForMode(mode);
    syncDraft(next.from, next.to);
  }

  function onMonth(year: number, month: number) {
    const next = monthClickPeriod(mode, year, month, draftFrom, pickingEnd);
    setDraftFrom(next.from);
    setDraftTo(next.to);
    setFromText(formatRuDate(next.from));
    setToText(formatRuDate(next.to));
    setPickingEnd(next.pickingEnd);
    setShowPresets(false);
  }

  function commitFromText() {
    const iso = parseRuDate(fromText);
    if (!iso) {
      setFromText(formatRuDate(draftFrom));
      return;
    }
    syncDraft(iso, draftTo);
  }

  function commitToText() {
    const iso = parseRuDate(toText);
    if (!iso) {
      setToText(formatRuDate(draftTo));
      return;
    }
    syncDraft(draftFrom, iso);
  }

  useLayoutEffect(() => {
    if (!open) {
      setPos(null);
      return;
    }
    function place() {
      const el = trigger.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const width = Math.min(760, Math.max(r.width, window.innerWidth - 24));
      let left = r.left;
      if (left + width > window.innerWidth - 12) left = Math.max(12, window.innerWidth - width - 12);
      setPos({ top: r.bottom + 4, left, width });
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
      closePanel();
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const start = parseIsoDate(draftFrom);
  const end = parseIsoDate(draftTo);
  const startIdx = start ? ymIndex(start.year, start.month) : 0;
  const endIdx = end ? ymIndex(end.year, end.month) : 0;
  const years = [windowStart, windowStart + 1, windowStart + 2];
  const canLeft = windowStart > minYear;
  const canRight = windowStart + 2 < maxYear + 2;

  return (
    <label className="field">
      <span>Период</span>
      <div className="period-cal" ref={root}>
        <button
          ref={trigger}
          type="button"
          className="period-cal-trigger"
          onClick={() => (open ? closePanel() : openPanel())}
          aria-expanded={open}
        >
          <span>
            {formatRuDate(from)} — {formatRuDate(to)}
          </span>
          <CalendarIcon />
        </button>
        {open &&
          pos &&
          createPortal(
            <div
              ref={pop}
              className="period-cal-pop"
              style={{ top: pos.top, left: pos.left, width: pos.width }}
            >
              <div className="period-cal-dates">
                <label className="period-cal-date">
                  <span>С</span>
                  <input
                    value={fromText}
                    onChange={(e) => setFromText(e.target.value)}
                    onBlur={commitFromText}
                    onKeyDown={(e) => e.key === "Enter" && commitFromText()}
                  />
                </label>
                <span className="period-cal-dash">—</span>
                <label className="period-cal-date">
                  <span>По</span>
                  <input
                    value={toText}
                    onChange={(e) => setToText(e.target.value)}
                    onBlur={commitToText}
                    onKeyDown={(e) => e.key === "Enter" && commitToText()}
                  />
                </label>
                <button type="button" className="period-cal-link" onClick={clearDraft}>
                  ✕ Очистить период
                </button>
              </div>

              <div className="period-cal-nav">
                <button
                  type="button"
                  className="period-cal-arrow"
                  disabled={!canLeft}
                  onClick={() => setWindowStart((y) => Math.max(minYear, y - 1))}
                  aria-label="Назад"
                >
                  ‹
                </button>
                <p className="period-cal-hint">{HINT[mode]}</p>
                <button
                  type="button"
                  className="period-cal-arrow"
                  disabled={!canRight}
                  onClick={() => setWindowStart((y) => y + 1)}
                  aria-label="Вперёд"
                >
                  ›
                </button>
              </div>

              {showPresets ? (
                <div className="period-cal-presets">
                  {standardPeriodOptions().map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className="period-cal-preset"
                      onClick={() => syncDraft(p.from, p.to)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="period-cal-years">
                  {years.map((year) => (
                    <div key={year} className="period-cal-year">
                      <div className="period-cal-year-title">{year}</div>
                      <div className="period-cal-months">
                        {MONTH_OPTIONS.map((opt, idx) => {
                          const month = idx + 1;
                          const idxYm = ymIndex(year, month);
                          const inRange = start && end && idxYm >= startIdx && idxYm <= endIdx;
                          const isStart = start && idxYm === startIdx;
                          const isEnd = end && idxYm === endIdx;
                          const disabled = year < minYear;
                          return (
                            <button
                              key={opt.value}
                              type="button"
                              disabled={disabled}
                              className={`period-cal-m${inRange ? " in" : ""}${isStart ? " start" : ""}${isEnd ? " end" : ""}`}
                              onClick={() => onMonth(year, month)}
                            >
                              {MONTHS_SHORT[idx]}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="period-cal-foot">
                <button type="button" className="period-cal-link" onClick={() => setShowPresets((v) => !v)}>
                  {showPresets ? "Показать календарь" : "Показать стандартные периоды"}
                </button>
                <div className="period-cal-actions">
                  <button type="button" className="btn secondary sm" onClick={closePanel}>
                    Отмена
                  </button>
                  <button type="button" className="btn sm" onClick={apply}>
                    Выбрать
                  </button>
                </div>
              </div>
            </div>,
            document.body,
          )}
      </div>
    </label>
  );
}
