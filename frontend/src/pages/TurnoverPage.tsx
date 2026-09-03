import { useState } from "react";
import { api } from "../api";

type Row = {
  counterparty?: string;
  dimension?: string;
  work_type?: string;
  work_type_percent?: number;
  sales: number;
  stock_begin: number;
  stock_end: number;
  stock_avg: number;
  turnover_percent: number;
  proposal?: number;
};

export default function TurnoverPage() {
  const [view, setView] = useState("main");
  const [year, setYear] = useState(2026);
  const [month, setMonth] = useState(5);
  const [rows, setRows] = useState<Row[]>([]);

  async function load() {
    const data = await api<{ data: Row[] }>(`/api/v1/reports/turnover?view=${view}&year=${year}&month=${month}`);
    setRows(data.data);
  }

  return (
    <>
      <h1>Оборачиваемость</h1>
      <div className="panel grid-2">
        <label className="field">Срез
          <select value={view} onChange={(e) => setView(e.target.value)}>
            <option value="main">Основной</option>
            <option value="lts">По ЖЦТ</option>
            <option value="counterparty">По контрагенту</option>
            <option value="wear_type">По типу ношения</option>
            <option value="metal_color">По цвету металла</option>
          </select>
        </label>
        <label className="field">Год<input type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} /></label>
        <label className="field">Месяц<input type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))} /></label>
        <div className="field"><span>&nbsp;</span><button className="btn" onClick={load}>Сформировать</button></div>
      </div>
      <div className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th className="sticky">Контрагент / измерение</th>
              <th>Тип работы</th>
              <th>%</th>
              <th>Ост. нач</th>
              <th>Ост. кон</th>
              <th>Продажи</th>
              <th>Об-ть %</th>
              <th>Предложение</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={idx}>
                <td className="sticky">{r.counterparty || r.dimension || "—"}</td>
                <td>{r.work_type || ""}</td>
                <td>{r.work_type_percent ?? ""}</td>
                <td>{Number(r.stock_begin)}</td>
                <td>{Number(r.stock_end)}</td>
                <td>{Number(r.sales)}</td>
                <td>{Number(r.turnover_percent)}</td>
                <td>{r.proposal != null ? Number(r.proposal) : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
