import { syncProgressView } from "../syncProgress";

type Props = {
  status: string;
  entity?: string;
  rowsDone?: number;
  rowsExpected?: number;
  rowsSynced?: number;
};

export default function SyncProgress({
  status,
  entity,
  rowsDone = 0,
  rowsExpected = 0,
  rowsSynced = 0,
}: Props) {
  const view = syncProgressView({ status, entity, rowsDone, rowsExpected, rowsSynced });
  return (
    <div className={`sync-progress is-${status}`}>
      <div
        className={`sync-progress-track${view.indeterminate ? " is-indeterminate" : ""}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={view.indeterminate ? undefined : view.fillPct}
        aria-label={view.label}
      >
        <span className="sync-progress-expected" />
        <span className="sync-progress-done" style={{ width: `${view.fillPct}%` }} />
      </div>
      <div className="sync-progress-meta">
        <span className={`sync-chip is-${status}`}>{view.label}</span>
        <span className="sync-progress-count">{view.detail}</span>
      </div>
    </div>
  );
}
