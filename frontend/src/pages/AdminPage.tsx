import { useEffect, useState } from "react";
import { api } from "../api";

type Sync = {
  source_id: string;
  entity: string;
  status: string;
  rows_synced: number;
  last_error?: string;
  last_incremental_at?: string;
};

type Health = { status: string; database: string; redis: string; odata: Record<string, string> };

export default function AdminPage() {
  const [sync, setSync] = useState<Sync[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [message, setMessage] = useState("");

  async function refresh() {
    setHealth(await api<Health>("/api/v1/health"));
    try {
      setSync(await api<Sync[]>("/api/v1/sync/status"));
    } catch {
      setSync([]);
    }
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  async function runSync(full: boolean) {
    setMessage("Синхронизация…");
    try {
      const result = await api<Record<string, unknown>>(`/api/v1/sync/run?full=${full}`, { method: "POST" });
      setMessage(JSON.stringify(result));
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Ошибка синка");
    }
  }

  return (
    <>
      <h1>Администрирование</h1>
      <div className="panel">
        <h2>Health</h2>
        {health && (
          <p>
            status={health.status}, db={health.database}, redis={health.redis}, odata={JSON.stringify(health.odata)}
          </p>
        )}
        <button className="btn" onClick={() => runSync(false)} style={{ marginRight: 8 }}>Инкремент sync (asil)</button>
        <button className="btn secondary" onClick={() => runSync(true)}>Полный sync</button>
        {message && <pre style={{ whiteSpace: "pre-wrap" }}>{message}</pre>}
      </div>
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>source</th>
              <th>entity</th>
              <th>status</th>
              <th>rows</th>
              <th>last incremental</th>
              <th>error</th>
            </tr>
          </thead>
          <tbody>
            {sync.map((s, idx) => (
              <tr key={idx}>
                <td>{s.source_id}</td>
                <td>{s.entity}</td>
                <td>{s.status}</td>
                <td>{s.rows_synced}</td>
                <td>{s.last_incremental_at || "—"}</td>
                <td>{s.last_error || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
