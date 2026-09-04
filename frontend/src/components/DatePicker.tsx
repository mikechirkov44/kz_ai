import { useEffect, useMemo, useRef, useState } from "react";

const DOW = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const MONTHS = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
];
const MONTHS_SHORT = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"];

type Panel = "days" | "months" | "years";

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function toIso(d: Date) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function parseIso(value?: string): Date | null {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

type Props = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

export default function DatePicker({ value, onChange, placeholder = "Выберите дату" }: Props) {
  const selected = parseIso(value);
  const today = new Date();
  const [open, setOpen] = useState(false);
  const [panel, setPanel] = useState<Panel>("days");
  const [view, setView] = useState(() => selected || today);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selected) setView(selected);
  }, [value]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    if (open) setPanel("days");
  }, [open]);

  const cells = useMemo(() => {
    const year = view.getFullYear();
    const month = view.getMonth();
    const first = new Date(year, month, 1);
    let startDow = first.getDay() - 1;
    if (startDow < 0) startDow = 6;
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const prevDays = new Date(year, month, 0).getDate();
    const out: { date: Date; current: boolean }[] = [];
    for (let i = startDow - 1; i >= 0; i -= 1) {
      out.push({ date: new Date(year, month - 1, prevDays - i), current: false });
    }
    for (let d = 1; d <= daysInMonth; d += 1) {
      out.push({ date: new Date(year, month, d), current: true });
    }
    while (out.length % 7 !== 0) {
      const last = out[out.length - 1].date;
      out.push({
        date: new Date(last.getFullYear(), last.getMonth(), last.getDate() + 1),
        current: false,
      });
    }
    return out;
  }, [view]);

  const decadeStart = Math.floor(view.getFullYear() / 12) * 12;
  const years = Array.from({ length: 12 }, (_, i) => decadeStart + i);

  const label = selected
    ? `${pad(selected.getDate())}.${pad(selected.getMonth() + 1)}.${selected.getFullYear()}`
    : placeholder;

  function shiftView(delta: number) {
    if (panel === "days") {
      setView(new Date(view.getFullYear(), view.getMonth() + delta, 1));
    } else if (panel === "months") {
      setView(new Date(view.getFullYear() + delta, view.getMonth(), 1));
    } else {
      setView(new Date(view.getFullYear() + delta * 12, view.getMonth(), 1));
    }
  }

  return (
    <div className="ui-date" ref={root}>
      <button type="button" className="ui-date-trigger" onClick={() => setOpen((v) => !v)}>
        <span>{label}</span>
        <span className="chev">▾</span>
      </button>
      {open && (
        <div className="ui-date-pop">
          <div className="ui-date-head">
            <button type="button" className="btn secondary sm" onClick={() => shiftView(-1)} aria-label="Назад">
              ←
            </button>
            <div className="ui-date-title">
              {panel === "days" && (
                <>
                  <button type="button" className="ui-date-title-btn" onClick={() => setPanel("months")}>
                    {MONTHS[view.getMonth()]}
                  </button>
                  <button type="button" className="ui-date-title-btn" onClick={() => setPanel("years")}>
                    {view.getFullYear()}
                  </button>
                </>
              )}
              {panel === "months" && (
                <button type="button" className="ui-date-title-btn" onClick={() => setPanel("years")}>
                  {view.getFullYear()}
                </button>
              )}
              {panel === "years" && (
                <span className="ui-date-title-static">
                  {decadeStart}–{decadeStart + 11}
                </span>
              )}
            </div>
            <button type="button" className="btn secondary sm" onClick={() => shiftView(1)} aria-label="Вперёд">
              →
            </button>
          </div>

          {panel === "days" && (
            <div className="ui-date-grid">
              {DOW.map((d) => (
                <div key={d} className="ui-date-dow">
                  {d}
                </div>
              ))}
              {cells.map(({ date, current }) => {
                const iso = toIso(date);
                const isSelected = value === iso;
                const isToday = toIso(today) === iso;
                return (
                  <button
                    key={iso + String(current)}
                    type="button"
                    className={`ui-date-day ${current ? "" : "muted"} ${isSelected ? "selected" : ""} ${isToday ? "today" : ""}`}
                    onClick={() => {
                      onChange(iso);
                      setOpen(false);
                    }}
                  >
                    {date.getDate()}
                  </button>
                );
              })}
            </div>
          )}

          {panel === "months" && (
            <div className="ui-date-months">
              {MONTHS_SHORT.map((name, idx) => {
                const active = view.getMonth() === idx;
                return (
                  <button
                    key={name}
                    type="button"
                    className={`ui-date-chip ${active ? "selected" : ""}`}
                    onClick={() => {
                      setView(new Date(view.getFullYear(), idx, 1));
                      setPanel("days");
                    }}
                  >
                    {name}
                  </button>
                );
              })}
            </div>
          )}

          {panel === "years" && (
            <div className="ui-date-months">
              {years.map((y) => {
                const active = view.getFullYear() === y;
                return (
                  <button
                    key={y}
                    type="button"
                    className={`ui-date-chip ${active ? "selected" : ""}`}
                    onClick={() => {
                      setView(new Date(y, view.getMonth(), 1));
                      setPanel("months");
                    }}
                  >
                    {y}
                  </button>
                );
              })}
            </div>
          )}

          <div className="ui-date-foot">
            <button
              type="button"
              className="btn secondary sm"
              onClick={() => {
                const t = new Date();
                onChange(toIso(t));
                setView(t);
                setOpen(false);
              }}
            >
              Сегодня
            </button>
            {panel !== "days" && (
              <button type="button" className="btn secondary sm" onClick={() => setPanel("days")}>
                К дням
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
