type Props = {
  label: string;
};

export default function ChartWait({ label }: Props) {
  return (
    <div className="chart-wait" role="status" aria-live="polite">
      <div className="chart-wait-bars" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
        <span />
      </div>
      <p>
        {label}
        <span className="ai-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </p>
    </div>
  );
}
