import { useMemo, useState } from "react";

export type DimMetrics = {
  dimension: string;
  avg_stock: number;
  sales_total: number;
  quarter_turnover_percent: number;
  avg_month_turnover_percent: number;
};

export type MatrixRow = {
  metal_color?: DimMetrics | null;
  lts?: DimMetrics | null;
  wear_type?: DimMetrics | null;
  is_total?: boolean;
};

export type RecItem = {
  message: string;
  type?: string;
  severity?: string;
};

export type SummaryClient = {
  counterparty_id: string;
  counterparty: string;
  work_type?: string | null;
  work_type_label?: string;
  work_type_percent?: number;
  plan: number;
  sales_total?: number;
  sales_prev_quarter: number;
  sales_prev2_quarter: number;
  dynamics_percent: number | null;
  comment: string | null;
  next_quarter_plan: number;
  recommendations_text: string;
  recommendations?: RecItem[];
  matrix: MatrixRow[];
  blocks?: Record<string, DimMetrics[]>;
  total?: DimMetrics;
};

export type SummaryLabels = {
  plan?: string;
  sales?: string;
  turnover?: string;
  avg_turnover?: string;
  sales_prev?: string;
  sales_prev2?: string;
  dynamics?: string;
  next_plan?: string;
};

export function qty(value: number | null | undefined): string {
  if (value == null) return "—";
  return Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
}

export function pct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
}

function turnClass(value?: number): string {
  if (value == null) return "";
  if (value < 10) return "turn-low";
  if (value < 30) return "turn-mid";
  return "turn-ok";
}

function dynClass(value: number | null): string {
  if (value == null) return "";
  if (value < 100) return "dyn-down";
  if (value > 100) return "dyn-up";
  return "";
}

function workPill(client: SummaryClient): string {
  const wt = (client.work_type || client.work_type_label || "").toLowerCase();
  if (wt.includes("рост") || wt.includes("growth")) return "pill ok";
  if (wt.includes("пад") || wt.includes("decline")) return "pill warn";
  return "pill";
}

type BlockKey = "metal_color" | "lts" | "wear_type";

const BLOCKS: { key: BlockKey; title: string; css: string }[] = [
  { key: "metal_color", title: "Цвет металла", css: "metal" },
  { key: "lts", title: "ЖЦТ", css: "lts" },
  { key: "wear_type", title: "Тип изделия", css: "wear" },
];

function rowsForBlock(client: SummaryClient, key: BlockKey): DimMetrics[] {
  const fromMatrix = client.matrix
    .filter((row) => !row.is_total)
    .map((row) => row[key])
    .filter((cell): cell is DimMetrics => Boolean(cell));
  const title = BLOCKS.find((b) => b.key === key)?.title;
  const fromBlocks = title ? client.blocks?.[title] : undefined;
  const rows = fromBlocks?.length ? fromBlocks : fromMatrix;
  const total = client.total || client.matrix.find((r) => r.is_total)?.[key] || undefined;
  if (total && !rows.some((r) => r.dimension === total.dimension)) {
    return [...rows, total];
  }
  return rows;
}

function recMessages(client: SummaryClient): string[] {
  if (client.recommendations?.length) {
    return client.recommendations.map((r) => r.message).filter(Boolean);
  }
  return client.recommendations_text ? [client.recommendations_text] : [];
}

type Props = {
  clients: SummaryClient[];
  labels?: SummaryLabels;
  onSaveComment?: (counterpartyId: string, text: string) => Promise<void>;
  onShowHistory?: (counterpartyId: string) => void;
};

export default function QuarterlyMatrix({ clients, onSaveComment, onShowHistory }: Props) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string>("");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return clients;
    return clients.filter((c) => c.counterparty.toLowerCase().includes(q));
  }, [clients, query]);

  async function save(id: string) {
    if (!onSaveComment) return;
    const text = (drafts[id] ?? "").trim();
    if (!text) return;
    setSaving(id);
    try {
      await onSaveComment(id, text);
      setDrafts((prev) => ({ ...prev, [id]: "" }));
    } finally {
      setSaving("");
    }
  }

  if (!clients.length) {
    return <p className="empty">Нет клиентов с продажами за выбранный квартал</p>;
  }

  return (
    <div className="qcards">
      <div className="qcards-bar">
        <input
          className="control"
          placeholder="Найти контрагента…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="muted">
          {filtered.length} из {clients.length}
        </span>
      </div>
      {!filtered.length && <p className="empty">Никого не найдено</p>}
      {filtered.map((client) => {
        const recs = recMessages(client);
        const sales = client.sales_total ?? client.total?.sales_total;
        return (
          <details key={client.counterparty_id} className="qcard" open={filtered.length <= 2}>
            <summary className="qcard-head">
              <div>
                <h3>{client.counterparty}</h3>
                <div className="qcard-pills">
                  <span className={workPill(client)}>{client.work_type_label || "—"}</span>
                  {client.work_type_percent ? <span className="pill">{qty(client.work_type_percent)}%</span> : null}
                </div>
              </div>
              <dl className="qcard-kpis">
                <div>
                  <dt>План</dt>
                  <dd>{qty(client.plan)}</dd>
                </div>
                <div>
                  <dt>Продажи</dt>
                  <dd>{qty(sales)}</dd>
                </div>
                <div>
                  <dt>Пред. кв.</dt>
                  <dd>{qty(client.sales_prev_quarter)}</dd>
                </div>
                <div>
                  <dt>Динамика</dt>
                  <dd className={dynClass(client.dynamics_percent)}>{pct(client.dynamics_percent)}</dd>
                </div>
                <div>
                  <dt>План след.</dt>
                  <dd>{qty(client.next_quarter_plan)}</dd>
                </div>
              </dl>
            </summary>

            <div className="qcard-blocks">
              {BLOCKS.map((block) => (
                <BlockTable
                  key={block.key}
                  title={block.title}
                  css={block.css}
                  rows={rowsForBlock(client, block.key)}
                />
              ))}
            </div>

            <footer className="qcard-foot">
              <div className="qcard-comment">
                <h4>Комментарий</h4>
                <p>{client.comment || "Пока нет комментария"}</p>
                {onSaveComment && (
                  <>
                    <textarea
                      rows={2}
                      placeholder="Новый комментарий"
                      value={drafts[client.counterparty_id] ?? ""}
                      onChange={(e) => setDrafts((prev) => ({ ...prev, [client.counterparty_id]: e.target.value }))}
                    />
                    <div className="qmatrix-comment-actions">
                      <button
                        className="btn sm"
                        disabled={saving === client.counterparty_id || !(drafts[client.counterparty_id] || "").trim()}
                        onClick={(e) => {
                          e.preventDefault();
                          save(client.counterparty_id);
                        }}
                      >
                        {saving === client.counterparty_id ? "…" : "Сохранить"}
                      </button>
                      {onShowHistory && (
                        <button
                          className="btn secondary sm"
                          onClick={(e) => {
                            e.preventDefault();
                            onShowHistory(client.counterparty_id);
                          }}
                        >
                          История
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
              <div className="qcard-recs">
                <h4>Рекомендации</h4>
                {!recs.length && <p>Недостаточно данных для рекомендаций</p>}
                {recs.length > 0 && (
                  <ul>
                    {recs.map((msg) => (
                      <li key={msg}>{msg}</li>
                    ))}
                  </ul>
                )}
              </div>
            </footer>
          </details>
        );
      })}
    </div>
  );
}

function BlockTable({
  title,
  css,
  rows,
}: {
  title: string;
  css: string;
  rows: DimMetrics[];
}) {
  return (
    <div className={`qblock qblock-${css}`}>
      <h4>{title}</h4>
      <table>
        <thead>
          <tr>
            <th>Категория</th>
            <th>Остаток</th>
            <th>Продажи</th>
            <th>Об-ть</th>
            <th>Ср. об-ть</th>
          </tr>
        </thead>
        <tbody>
          {!rows.length && (
            <tr>
              <td colSpan={5} className="muted">
                Нет данных
              </td>
            </tr>
          )}
          {rows.map((row) => (
            <tr key={row.dimension} className={row.dimension === "Итого" ? "qblock-total" : undefined}>
              <td>{row.dimension}</td>
              <td className="num">{qty(row.avg_stock)}</td>
              <td className="num">{qty(row.sales_total)}</td>
              <td className={`num ${turnClass(row.quarter_turnover_percent)}`}>{pct(row.quarter_turnover_percent)}</td>
              <td className={`num ${turnClass(row.avg_month_turnover_percent)}`}>{pct(row.avg_month_turnover_percent)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
