import {
  heatmapCellKey,
  heatmapDuplicateNames,
  heatmapRowLabel,
  normalizeHeatmapCounterparties,
  type HeatmapCell,
  type HeatmapCounterpartyInput,
} from "../heatmapRows";

type Props = {
  counterparties: HeatmapCounterpartyInput[];
  articles: string[];
  articleNames?: Record<string, string>;
  cells: HeatmapCell[];
  sourceLabel?: (sourceId: string) => string;
};

function bucketClass(months: number): string {
  if (months <= 1) return "dwell-fresh";
  if (months <= 3) return "dwell-warm";
  if (months <= 6) return "dwell-stale";
  return "dwell-dead";
}

function prettyArticle(article: string): string {
  const text = article.trim();
  if (/^\d+$/.test(text)) return String(Number(text));
  return text;
}

export default function DwellHeatmap({
  counterparties,
  articles,
  articleNames = {},
  cells,
  sourceLabel,
}: Props) {
  const rows = normalizeHeatmapCounterparties(counterparties);
  const duplicateNames = heatmapDuplicateNames(rows);
  const map = new Map<string, HeatmapCell>();
  for (const cell of cells) {
    const rowId = cell.counterparty_id || cell.counterparty || "";
    map.set(heatmapCellKey(rowId, cell.article), cell);
  }

  if (!rows.length || !articles.length) {
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
              <th className="heatmap-corner">Клиент</th>
              {articles.map((a) => {
                const name = articleNames[a];
                const code = prettyArticle(a);
                return (
                  <th key={a} className="heatmap-sku" title={name ? `${a} · ${name}` : a}>
                    <span className="heatmap-sku-name">{name || code}</span>
                    {name ? <span className="heatmap-sku-code">{code}</span> : null}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const label = heatmapRowLabel(row, duplicateNames, sourceLabel);
              return (
                <tr key={row.id}>
                  <th className="heatmap-corner" title={label}>
                    {label}
                  </th>
                  {articles.map((art) => {
                    const cell = map.get(heatmapCellKey(row.id, art)) || map.get(heatmapCellKey(row.name, art));
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
                        title={`${label} · ${art}: залежалый товар ${cell.months_without_sales} мес., остаток ${cell.stock_qty}`}
                      >
                        {cell.months_without_sales}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
