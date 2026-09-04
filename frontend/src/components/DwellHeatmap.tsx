type Cell = {
  counterparty: string;
  article: string;
  months_without_sales: number;
  stock_qty: number;
};

type Props = {
  counterparties: string[];
  articles: string[];
  cells: Cell[];
};

function bucketClass(months: number): string {
  if (months <= 1) return "dwell-fresh";
  if (months <= 3) return "dwell-warm";
  if (months <= 6) return "dwell-stale";
  return "dwell-dead";
}

export default function DwellHeatmap({ counterparties, articles, cells }: Props) {
  const map = new Map<string, Cell>();
  for (const c of cells) {
    map.set(`${c.counterparty}|${c.article}`, c);
  }

  if (!counterparties.length || !articles.length) {
    return <p className="empty">Нет остатков для теплокарты — загрузите Excel продаж и остатков по акционным клиентам.</p>;
  }

  return (
    <div className="heatmap-wrap">
      <div className="heatmap-legend">
        <span className="dwell-fresh">0–1 мес.</span>
        <span className="dwell-warm">2–3</span>
        <span className="dwell-stale">4–6</span>
        <span className="dwell-dead">7+</span>
      </div>
      <div className="heatmap-scroll">
        <table className="heatmap">
          <thead>
            <tr>
              <th>Клиент</th>
              {articles.map((a) => (
                <th key={a} title={a}>
                  {a}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {counterparties.map((cp) => (
              <tr key={cp}>
                <th title={cp}>{cp}</th>
                {articles.map((art) => {
                  const cell = map.get(`${cp}|${art}`);
                  if (!cell) {
                    return (
                      <td key={art} className="dwell-empty">
                        —
                      </td>
                    );
                  }
                  return (
                    <td
                      key={art}
                      className={bucketClass(cell.months_without_sales)}
                      title={`${cp} · ${art}: пролежка ${cell.months_without_sales} мес., остаток ${cell.stock_qty}`}
                    >
                      {cell.months_without_sales}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
