import {
  recActionLabel,
  recSeverityLabel,
  recTypeLabel,
  recWhyChips,
  type Recommendation,
} from "../recommendations";

type Props = {
  item: Recommendation;
  compact?: boolean;
  hideClient?: boolean;
  delay?: number;
};

export default function RecommendationCard({ item, compact = false, hideClient = false, delay = 0 }: Props) {
  const score = Math.max(0, Math.min(100, item.score || 0));
  const chips = recWhyChips(item);
  return (
    <article
      className={`panel rec-card ${item.severity} ${compact ? "compact" : ""}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="rec-card-head">
        <div className="rec-card-pills">
          <span className="pill">{recTypeLabel(item.type)}</span>
          <span className={`pill ${item.severity === "high" ? "bad" : item.severity === "medium" ? "warn" : "ok"}`}>
            {recSeverityLabel(item.severity)}
          </span>
          {item.action && <span className="pill rec-action">{recActionLabel(item.action)}</span>}
          {item.llm_comment && <span className="pill">ИИ</span>}
        </div>
        {score > 0 && (
          <div className="rec-score" title={`Приоритет ${score}`}>
            <span>{score}</span>
            <i style={{ width: `${score}%` }} />
          </div>
        )}
      </div>
      {(hideClient ? item.article : item.counterparty || item.article) && (
        <div className="muted rec-who">
          {hideClient ? item.article : `${item.counterparty || ""}${item.article ? ` · ${item.article}` : ""}`}
        </div>
      )}
      {item.title && <h3 className="rec-title">{item.title}</h3>}
      <p className="rec-message">{item.message}</p>
      {!!chips.length && !compact && (
        <div className="rec-why">
          {chips.map((chip) => (
            <span key={chip} className="pill">
              {chip}
            </span>
          ))}
        </div>
      )}
      {item.llm_comment && (
        <div className="rec-llm">
          <div className="rec-llm-label">Совет ИИ</div>
          {item.llm_comment}
        </div>
      )}
    </article>
  );
}
