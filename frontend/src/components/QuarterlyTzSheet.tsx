import type { DimMetrics, MatrixRow, SummaryClient, SummaryLabels } from "./QuarterlyMatrix";

function qty(value: number | null | undefined): string {
  if (value == null) return "";
  return Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
}

function pct(value: number | null | undefined): string {
  if (value == null) return "";
  return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
}

function cell(row: MatrixRow | undefined, key: "metal_color" | "lts" | "wear_type"): DimMetrics | null {
  return row?.[key] || null;
}

function DimTds({ dim }: { dim: DimMetrics | null }) {
  if (!dim) {
    return (
      <>
        <td />
        <td className="num" />
        <td className="num" />
        <td className="num" />
        <td className="num" />
      </>
    );
  }
  return (
    <>
      <td>{dim.dimension}</td>
      <td className="num">{qty(dim.avg_stock)}</td>
      <td className="num">{qty(dim.sales_total)}</td>
      <td className="num">{pct(dim.quarter_turnover_percent)}</td>
      <td className="num">{pct(dim.avg_month_turnover_percent)}</td>
    </>
  );
}

type Props = {
  year: number;
  quarter: number;
  labels?: SummaryLabels;
  clients: SummaryClient[];
};

export default function QuarterlyTzSheet({ year, quarter, labels = {}, clients }: Props) {
  const metricHeads = [
    "категория",
    "ср остаток на квартал",
    labels.sales || "итого продажи",
    labels.turnover || "Об-ть квартала",
    labels.avg_turnover || "Ср. об-ть за квартал",
  ];

  return (
    <div className="tz-scroll">
      <table className="tz-sheet">
        <thead>
          <tr>
            <th rowSpan={2}>Контрагент</th>
            <th rowSpan={2}>Тип работы контрагента</th>
            <th rowSpan={2}>% типа работ</th>
            <th rowSpan={2}>{labels.plan || "План отгрузки"}</th>
            <th colSpan={5} className="blk-metal">
              Цвет металла
            </th>
            <th colSpan={5} className="blk-lts">
              ЖЦТ
            </th>
            <th colSpan={5} className="blk-wear">
              Тип изделия
            </th>
            <th rowSpan={2}>{labels.sales_prev || "продажи пред. кв."}</th>
            <th rowSpan={2}>{labels.sales_prev2 || "продажи предпред. кв."}</th>
            <th rowSpan={2}>{labels.dynamics || "Динамика"}</th>
            <th rowSpan={2}>Комментарий</th>
            <th rowSpan={2}>{labels.next_plan || "План след. кв (шт)"}</th>
            <th rowSpan={2}>Рекомендации</th>
          </tr>
          <tr>
            {[0, 1, 2].flatMap((block) =>
              metricHeads.map((title) => (
                <th key={`${block}-${title}`}>{title}</th>
              )),
            )}
          </tr>
        </thead>
        <tbody>
          {!clients.length && (
            <tr>
              <td colSpan={25}>Нет клиентов с продажами за {year} Q{quarter}</td>
            </tr>
          )}
          {clients.map((client) => {
            const body = (client.matrix || []).filter((row) => !row.is_total);
            const total = (client.matrix || []).find((row) => row.is_total);
            return (
              <ClientBlock
                key={client.counterparty_id}
                client={client}
                body={body}
                total={total}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ClientBlock({
  client,
  body,
  total,
}: {
  client: SummaryClient;
  body: MatrixRow[];
  total?: MatrixRow;
}) {
  const span = body.length + (total ? 1 : 0) || 1;
  return (
    <>
      {body.map((row, idx) => (
        <tr key={`${client.counterparty_id}-r-${idx}`}>
          {idx === 0 && <IdentityCells client={client} span={span} />}
          <DimTds dim={cell(row, "metal_color")} />
          <DimTds dim={cell(row, "lts")} />
          <DimTds dim={cell(row, "wear_type")} />
          <td />
          <td />
          <td />
          <td />
          <td />
          <td />
        </tr>
      ))}
      {total && (
        <tr className="tz-total">
          {body.length === 0 && <IdentityCells client={client} span={1} />}
          <DimTds dim={cell(total, "metal_color")} />
          <DimTds dim={cell(total, "lts")} />
          <DimTds dim={cell(total, "wear_type")} />
          <td className="num">{qty(client.sales_prev_quarter)}</td>
          <td className="num">{qty(client.sales_prev2_quarter)}</td>
          <td className="num">{pct(client.dynamics_percent)}</td>
          <td className="tz-text">{client.comment || ""}</td>
          <td className="num">{qty(client.next_quarter_plan)}</td>
          <td className="tz-text">{client.recommendations_text || ""}</td>
        </tr>
      )}
      <tr className="tz-gap">
        <td colSpan={25} />
      </tr>
    </>
  );
}

function IdentityCells({ client, span }: { client: SummaryClient; span: number }) {
  return (
    <>
      <td rowSpan={span} className="tz-name">
        {client.counterparty}
      </td>
      <td rowSpan={span}>{client.work_type_label || ""}</td>
      <td rowSpan={span} className="num">
        {qty(client.work_type_percent)}
      </td>
      <td rowSpan={span} className="num">
        {qty(client.plan)}
      </td>
    </>
  );
}
