import { useEffect, useMemo, useState } from "react";
import { listODataSources, type ODataSourceOption } from "./api";

export type { ODataSourceOption };

export function sourceLabel(sourceId: string, sources: { source_id: string; label: string }[]): string {
  return sources.find((s) => s.source_id === sourceId)?.label || sourceId;
}

export function useODataSources(preset?: ODataSourceOption[]) {
  const [fetched, setFetched] = useState<ODataSourceOption[]>([]);

  useEffect(() => {
    if (preset) return;
    listODataSources()
      .then(setFetched)
      .catch(() => setFetched([]));
  }, [preset]);

  const sources = preset ?? fetched;
  const labelOf = useMemo(() => {
    const map: Record<string, string> = {};
    for (const s of sources) map[s.source_id] = s.label || s.source_id;
    return (id: string) => map[id] || id;
  }, [sources]);

  return { sources, labelOf };
}
