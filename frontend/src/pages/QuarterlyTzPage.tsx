import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, downloadFile } from "../api";
import QuarterlyTzSheet from "../components/QuarterlyTzSheet";
import { ExcelLabel } from "../components/ExcelIcon";
import type { SummaryClient, SummaryLabels, SummaryReport } from "../components/QuarterlyMatrix";
import { usePageTitle } from "../usePageTitle";

function summaryQuery(year: number, quarter: number, includeEmpty: boolean): string {
  const params = new URLSearchParams({
    year: String(year),
    quarter: String(quarter),
  });
  if (includeEmpty) params.set("include_empty", "true");
  return params.toString();
}

function excelQuery(
  year: number,
  quarter: number,
  includeEmpty: boolean,
  filters: { query: string; workType: string; manager: string },
  enrich = false,
): string {
  const params = new URLSearchParams(summaryQuery(year, quarter, includeEmpty));
  if (filters.query.trim()) params.set("q", filters.query.trim());
  if (filters.workType.trim()) params.set("work_type", filters.workType.trim());
  if (filters.manager.trim()) params.set("manager", filters.manager.trim());
  if (enrich) params.set("enrich", "true");
  return params.toString();
}

export default function QuarterlyTzPage() {
  const [params] = useSearchParams();
  const year = Number(params.get("year") || new Date().getFullYear());
  const quarter = Number(params.get("quarter") || 1);
  usePageTitle(`Итоговый отчёт ${year} Q${quarter}`);
  const [clients, setClients] = useState<SummaryClient[]>([]);
  const [labels, setLabels] = useState<SummaryLabels>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [includeEmpty, setIncludeEmpty] = useState(false);
  const [query, setQuery] = useState("");
  const [workType, setWorkType] = useState("");
  const [manager, setManager] = useState("");
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [llmStatus, setLlmStatus] = useState("off");
  const [llmError, setLlmError] = useState("");
  const [enriching, setEnriching] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError("");
    setEnriching(false);
    api<SummaryReport>(
      `/api/v1/reports/quarterly-summary?${summaryQuery(year, quarter, includeEmpty)}`,
    )
      .then((sum) => {
        setClients(sum.clients || []);
        setLabels(sum.labels || {});
        setLlmEnabled(Boolean(sum.llm_enabled));
        setLlmStatus("off");
        setLlmError("");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Ошибка"))
      .finally(() => setLoading(false));
  }, [year, quarter, includeEmpty]);

  function enrichSummary() {
    setEnriching(true);
    setError("");
    api<SummaryReport>(
      `/api/v1/reports/quarterly-summary/enrich?${summaryQuery(year, quarter, includeEmpty)}`,
      {
        method: "POST",
        body: JSON.stringify({ year, quarter, labels, clients }),
      },
    )
      .then((sum) => {
        setClients(sum.clients || []);
        setLabels(sum.labels || labels);
        setLlmEnabled(Boolean(sum.llm_enabled) || llmEnabled);
        setLlmStatus(sum.llm_status || "error");
        setLlmError(sum.llm_error || "");
      })
      .catch((err) => {
        setLlmStatus("error");
        setLlmError(err instanceof Error ? err.message : "Нет ответа модели");
        setError(err instanceof Error ? err.message : "Ошибка ИИ");
      })
      .finally(() => setEnriching(false));
  }

  return (
    <div className="tz-page">
      <div className="tz-toolbar no-print">
        <div>
          <h1>
            Итоговый отчёт по кварталу · {year} Q{quarter}
          </h1>
        </div>
        <div className="toolbar">
          <Link className="btn secondary" to="/quarterly">
            ← К отчёту
          </Link>
          <button
            className="btn secondary"
            onClick={() =>
              downloadFile(
                `/api/v1/reports/quarterly-summary.xlsx?${excelQuery(year, quarter, includeEmpty, { query, workType, manager }, llmStatus === "ok")}`,
                `quarterly_summary_Q${quarter}_${year}.xlsx`,
              ).catch((err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"))
            }
          >
            <ExcelLabel>Скачать Excel</ExcelLabel>
          </button>
          <button className="btn" onClick={() => window.print()}>
            Печать
          </button>
        </div>
      </div>
      {error && <div className="alert">{error}</div>}
      {loading ? (
        <p className="empty">Загрузка…</p>
      ) : (
          <QuarterlyTzSheet
          year={year}
          quarter={quarter}
          labels={labels}
          clients={clients}
          defaultExpanded
          includeEmpty={includeEmpty}
          onIncludeEmptyChange={setIncludeEmpty}
          query={query}
          onQueryChange={setQuery}
          workType={workType}
          onWorkTypeChange={setWorkType}
          manager={manager}
          onManagerChange={setManager}
          llmEnabled={llmEnabled}
          llmStatus={llmStatus}
          llmError={llmError}
          enriching={enriching}
          onEnrich={enrichSummary}
        />
      )}
    </div>
  );
}
