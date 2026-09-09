import { useLayoutEffect, useRef } from "react";

/** Stretch an element down to the bottom of the viewport. */
export function useFillRemainingHeight(bottomGap = 16, deps: unknown[] = []) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    const apply = () => {
      const top = el.getBoundingClientRect().top;
      const next = `${Math.max(280, Math.floor(window.innerHeight - top - bottomGap))}px`;
      if (el.style.height !== next) el.style.height = next;
    };

    apply();
    window.addEventListener("resize", apply);
    const parent = el.parentElement;
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(apply) : null;
    if (parent) ro?.observe(parent);
    return () => {
      window.removeEventListener("resize", apply);
      ro?.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bottomGap, ...deps]);

  return ref;
}
