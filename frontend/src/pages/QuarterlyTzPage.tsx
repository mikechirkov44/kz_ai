import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, downloadFile } from "../api";
import QuarterlyTzSheet from "../components/QuarterlyTzSheet";
import type { SummaryClient, SummaryLabels } from "../components/QuarterlyMatrix";

export default function QuarterlyTzPage() {
  const [params] = useSearchParams();
  const year = Number(params.get("year") || new Date().getFullYear());
  const quarter = Number(params.get("quarter") || 1);
  const [clients, setClients] = useState<SummaryClient[]>([]);
  const [labels, setLabels] = useState<SummaryLabels>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError("");
    api<{ clients: SummaryClient[]; labels: SummaryLabels }>(
      `/api/v1/reports/quarterly-summary?year=${year}&quarter=${quarter}`,
    )
      .then((sum) => {
        setClients(sum.clients || []);
        setLabels(sum.labels || {});
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Ошибка"))
      .finally(() => setLoading(false));
  }, [year, quarter]);

  return (
    <div className="tz-page">
      <div className="tz-toolbar no-print">
        <div>
          <h1>Итоговый отчёт по кварталу · {year} Q{quarter}</h1>
        </div>
        <div className="toolbar">
          <Link className="btn secondary" to="/quarterly">
            ← К отчёту
          </Link>
          <button
            className="btn secondary"
            onClick={() =>
              downloadFile(
                `/api/v1/reports/quarterly-summary.xlsx?year=${year}&quarter=${quarter}`,
                `quarterly_summary_Q${quarter}_${year}.xlsx`,
              ).catch((err) => setError(err instanceof Error ? err.message : "Ошибка экспорта"))
            }
          >
            Скачать Excel
          </button>
          <button className="btn" onClick={() => window.print()}>
            Печать
          </button>
        </div>
      </div>
      {error && <div className="alert">{error}</div>}
      {loading ? <p className="empty">Загрузка…</p> : <QuarterlyTzSheet year={year} quarter={quarter} labels={labels} clients={clients} />}
    </div>
  );
}
