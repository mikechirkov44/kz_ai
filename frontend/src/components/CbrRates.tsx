export type CbrRateItem = {
  code: string;
  name: string;
  rate: number;
  change_percent?: number | null;
  history: { date: string; rate: number }[];
};

export type CbrRatesResponse = {
  as_of?: string | null;
  status: string;
  source?: string;
  items: CbrRateItem[];
};

export function formatCbrRate(rate: number): string {
  const digits = rate < 1 ? 4 : 2;
  return `${rate.toLocaleString("ru-RU", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })} ₽`;
}

export function formatCbrChange(change?: number | null): string {
  if (change == null || Number.isNaN(change)) return "—";
  const abs = Math.abs(change).toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (change > 0) return `+${abs}%`;
  if (change < 0) return `−${abs}%`;
  return `${abs}%`;
}

function Sparkline({ values, down }: { values: number[]; down: boolean }) {
  if (values.length < 2) return <span className="cbr-spark-empty" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 96;
  const height = 36;
  const pad = 2;
  const points = values
    .map((value, idx) => {
      const x = pad + (idx / (values.length - 1)) * (width - pad * 2);
      const y = height - pad - ((value - min) / span) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="cbr-spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <polyline fill="none" stroke={down ? "var(--bad)" : "var(--ok)"} strokeWidth="1.8" strokeLinejoin="round" points={points} />
    </svg>
  );
}

function unitHint(code: string): string {
  if (code === "KZT") return "за 1 ₸";
  if (code === "USD") return "за 1 $";
  if (code === "EUR") return "за 1 €";
  return "за 1";
}

export default function CbrRates({ data }: { data: CbrRatesResponse | null }) {
  if (!data?.items.length) {
    return (
      <div className="cbr-rates muted">
        {data?.status === "error" ? "Курс ЦБ РФ недоступен" : "Загрузка курса ЦБ РФ…"}
      </div>
    );
  }

  return (
    <div className="cbr-rates" aria-label="Курсы ЦБ РФ">
      {data.items.map((item) => {
        const change = item.change_percent ?? 0;
        const down = change < 0;
        const values = item.history.map((point) => Number(point.rate));
        return (
          <article key={item.code} className="cbr-rate">
            <div className="cbr-rate-head">
              <span className="cbr-rate-code">{item.code}</span>
              <span className={`cbr-rate-change ${down ? "down" : "up"}`}>{formatCbrChange(item.change_percent)}</span>
            </div>
            <div className="cbr-rate-foot">
              <div>
                <div className="cbr-rate-value">{formatCbrRate(Number(item.rate))}</div>
                <div className="cbr-rate-unit">{unitHint(item.code)}</div>
              </div>
              <Sparkline values={values} down={down} />
            </div>
          </article>
        );
      })}
    </div>
  );
}
