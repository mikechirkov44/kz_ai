import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { ChartSlice } from "../dashboardCharts";

type Props = {
  data: ChartSlice[];
  empty: string;
};

export default function DashDonut({ data, empty }: Props) {
  if (!data.length) return <p className="empty">{empty}</p>;
  const total = data.reduce((sum, row) => sum + row.value, 0);
  return (
    <div className="dash-donut">
      <div className="dash-donut-chart">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} paddingAngle={2}>
              {data.map((row) => (
                <Cell key={row.name} fill={row.fill} />
              ))}
            </Pie>
            <Tooltip formatter={(value: number, name: string) => [`${value}`, name]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="dash-donut-legend">
        {data.map((row) => (
          <li key={row.name}>
            <span className="dash-swatch" style={{ background: row.fill }} />
            <span>{row.name}</span>
            <strong>{row.value}</strong>
            <span className="muted">{total ? Math.round((row.value / total) * 100) : 0}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
