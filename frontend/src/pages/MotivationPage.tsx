import { useEffect, useState } from "react";
import { api, gradeClass } from "../api";

type CP = { id: string; name: string };
type Report = {
  counterparty: string;
  period: string;
  total_bonus: number;
  items: { article: string; price: number; quantity: number; grade: string; bonus_per_unit: number; total_bonus: number }[];
};

export default function MotivationPage() {
  const [cps, setCps] = useState<CP[]>([]);
  const [cpId, setCpId] = useState("");
  const [year, setYear] = useState(2026);
  const [month, setMonth] = useState(1);
  const [report, setReport] = useState<Report | null>(null);

  useEffect(() => {
    api<CP[]>("/api/v1/counterparties?promo_only=true").then((rows) => {
      setCps(rows);
      if (rows[0]) setCpId(rows[0].id);
    }).catch(() => setCps([]));
  }, []);

  async function load() {
    if (!cpId) return;
    const data = await api<Report>(`/api/v1/reports/motivation?counterparty_id=${cpId}&year=${year}&month=${month}`);
    setReport(data);
  }

  return (
    <>
      <h1>Расчёт мотивации</h1>
      <div className="panel grid-2">
        <label className="field">Контрагент
          <select value={cpId} onChange={(e) => setCpId(e.target.value)}>
            {cps.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">Год<input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} /></label>
        <label className="field">Месяц<input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))} /></label>
        <div className="field"><span>&nbsp;</span><button className="btn" onClick={load}>Сформировать</button></div>
      </div>
      {report && (
        <div className="panel">
          <h2>{report.counterparty} · {report.period}</h2>
          <p>Итого бонус: <strong>{Number(report.total_bonus).toLocaleString("ru-RU")} тг</strong></p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="sticky">Артикул</th>
                  <th>Цена</th>
                  <th>Кол-во</th>
                  <th>Грейд</th>
                  <th>Бонус/шт</th>
                  <th>Итого</th>
                </tr>
              </thead>
              <tbody>
                {report.items.map((item, idx) => (
                  <tr key={idx}>
                    <td className="sticky">{item.article}</td>
                    <td>{Number(item.price).toLocaleString("ru-RU")}</td>
                    <td>{Number(item.quantity)}</td>
                    <td className={gradeClass(item.grade)}>{item.grade}</td>
                    <td>{Number(item.bonus_per_unit).toLocaleString("ru-RU")}</td>
                    <td>{Number(item.total_bonus).toLocaleString("ru-RU")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
