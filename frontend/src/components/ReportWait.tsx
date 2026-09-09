import { useEffect, useState } from "react";
import { MOTIVATION_WAIT_STEPS, waitStepAt } from "../reportWait";

type Props = {
  title?: string;
  compact?: boolean;
  steps?: readonly string[];
};

export default function ReportWait({
  title = "Считаю мотивацию",
  compact = false,
  steps = MOTIVATION_WAIT_STEPS,
}: Props) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setElapsed((value) => value + 400), 400);
    return () => window.clearInterval(id);
  }, []);
  const step = waitStepAt(elapsed, steps);

  return (
    <div className={`report-wait ${compact ? "is-compact" : ""}`} aria-busy="true" aria-live="polite">
      <span className="report-wait-pulse" aria-hidden />
      <div className="report-wait-body">
        <strong>{title}</strong>
        <p>
          {step}
          <span className="ai-dots" aria-hidden>
            <i />
            <i />
            <i />
          </span>
        </p>
      </div>
    </div>
  );
}
