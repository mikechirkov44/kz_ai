import { useEffect, useRef, useState, type ReactNode } from "react";
import { useFillRemainingHeight } from "../useFillRemainingHeight";

type Props = {
  children: ReactNode;
  deps?: unknown[];
};

export default function TzScrollPane({ children, deps = [] }: Props) {
  const paneRef = useFillRemainingHeight(16, deps);
  const mainRef = useRef<HTMLDivElement>(null);
  const [wide, setWide] = useState(false);

  useEffect(() => {
    const main = mainRef.current;
    if (!main) return;
    const check = () => {
      setWide(main.scrollWidth > main.clientWidth + 8);
      const table = main.querySelector("table");
      const row1 = table?.querySelector("thead tr");
      if (table instanceof HTMLElement && row1 instanceof HTMLElement) {
        const head = Math.round(row1.getBoundingClientRect().height);
        if (head > 0) table.style.setProperty("--tz-head-1", `${head}px`);
      }
    };
    check();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(check) : null;
    ro?.observe(main);
    const table = main.querySelector("table");
    if (table) ro?.observe(table);
    window.addEventListener("resize", check);
    return () => {
      ro?.disconnect();
      window.removeEventListener("resize", check);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return (
    <div className="tz-pane" ref={paneRef}>
      {wide && <p className="wide-table-hint no-print">Листайте таблицу вправо →</p>}
      <div className={`tz-scroll${wide ? " is-wide" : ""}`} ref={mainRef}>
        {children}
      </div>
    </div>
  );
}
