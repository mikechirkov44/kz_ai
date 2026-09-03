import { useState } from "react";
import { api } from "../api";

type Row = { counterparty: string; plan: number; fact: number; percent: number; dynamics?: number };

export default function QuarterlyPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [quarter, setQuarter] = useState(Math.floor(new Date().getMonth() / 3) + 1);
  const [rows, setRows] = useState<Row[]>([]);

  async function load() {
    const data = await api<{ clients: Row[] }>(`/api/v1/reports/quarterly-plans?year=${year}&quarter=${quarter}`);
    setRows(data.clients);
  }

  return (
    <>
      <h1>Квартальные планы</h1>
      <div className="panel grid-2">
        <label className="field">Год<input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} /></label>
        <label className="field">Квартал<input type="number" min={1} max={4} value={quarter} onChange={(e) => setQuarter(Number(e.target.value))} /></label>
        <div className="field"><span>&nbsp;</span><button className="btn" onClick={load}>Обновить</button></div>
      </div>
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th className="sticky">Контрагент</th>
              <th>План</th>
              <th>Факт</th>
              <th>% выполнения</th>
              <th>Динамика</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={idx}>
                <td className="sticky">{r.counterparty}</td>
                <td>{Number(r.plan).toLocaleString("ru-RU")}</td>
                <td>{Number(r.fact).toLocaleString("ru-RU")}</td>
                <td>{Number(r.percent)}</td>
                <td>{r.dynamics ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
