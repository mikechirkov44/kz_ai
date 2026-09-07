import RecText from "./RecText";
import {
  briefingPhase,
  briefingStatusText,
  recActionCounts,
  recActionLabel,
  type RecAction,
  type Recommendation,
} from "../recommendations";

type Props = {
  summary?: string;
  llmStatus: string;
  thinking?: boolean;
  enriching?: boolean;
  count?: number;
  items?: Recommendation[];
  onOpenReport?: () => void;
};

const DIGEST_ACTIONS: RecAction[] = ["return", "restock", "transfer", "reprice"];

export default function AiBriefing({
  summary = "",
  llmStatus,
  thinking = false,
  enriching = false,
  count = 0,
  items = [],
  onOpenReport,
}: Props) {
  const phase = briefingPhase({ thinking, enriching, llmStatus });
  const busy = phase === "loading" || phase === "enriching";
  const status = briefingStatusText(phase);
  const showDigest = phase === "ok" && !!summary;
  const counts = recActionCounts(items);
  return (
    <section
      className={["ai-brief", busy ? "thinking" : "", phase === "ok" ? "ready" : "", phase === "error" ? "quiet" : ""]
        .filter(Boolean)
        .join(" ")}
      aria-live="polite"
    >
      <div className={["ai-brief-orb", busy || phase === "ok" ? "live" : ""].filter(Boolean).join(" ")} aria-hidden="true">
        <span className="ai-brief-ring" />
        <span className="ai-brief-ring" />
        <span className="ai-brief-spark" />
        <span className="ai-brief-core" />
      </div>
      <div className="ai-brief-body">
        <div className="ai-brief-meta">
          <h2>Ассистент</h2>
          {status ? (
            <span className={`ai-brief-status ${phase === "ok" ? "ok" : ""} ${phase === "error" ? "warn" : ""}`}>
              {status}
              {busy ? (
                <span className="ai-dots">
                  <i />
                  <i />
                  <i />
                </span>
              ) : null}
            </span>
          ) : null}
          {!busy && count > 0 && <span className="muted">{count}</span>}
        </div>
        {showDigest ? (
          <div className="ai-brief-summary">
            <p>
              <RecText text={summary} />
            </p>
            <div className="ai-digest-stats">
              {DIGEST_ACTIONS.map((action) => (
                <span key={action} className={`ai-digest-stat ${counts[action] ? "" : "is-empty"}`}>
                  <strong>{counts[action]}</strong>
                  {recActionLabel(action)}
                </span>
              ))}
            </div>
            {onOpenReport ? (
              <div className="ai-brief-actions">
                <button type="button" className="btn" onClick={onOpenReport}>
                  Открыть аналитический отчёт
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
