import RecText from "./RecText";
import PriceGapMeter from "./PriceGapMeter";
import {
  priceArticleRows,
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
  awaitingLlm?: boolean;
};

export default function RecommendationCard({
  item,
  compact = false,
  hideClient = false,
  delay = 0,
  awaitingLlm = false,
}: Props) {
  const score = Math.max(0, Math.min(100, item.score || 0));
  const chips = recWhyChips(item);
  const articles = priceArticleRows(item.details);
  const showWait = awaitingLlm && !item.llm_comment && !compact;
  return (
    <article
      className={[
        "panel rec-card",
        item.severity,
        compact ? "compact" : "",
        item.llm_comment ? "has-llm" : "",
        showWait ? "awaiting-llm" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="rec-card-head">
        <div className="rec-card-pills">
          <span className="pill">{recTypeLabel(item.type)}</span>
          <span className={`pill ${item.severity === "high" ? "bad" : item.severity === "medium" ? "warn" : "ok"}`}>
            {recSeverityLabel(item.severity)}
          </span>
          {item.action && <span className="pill rec-action">{recActionLabel(item.action)}</span>}
          {item.llm_comment ? <span className="pill rec-ai">ИИ</span> : null}
          {showWait ? <span className="pill rec-ai is-wait">ИИ</span> : null}
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
      {item.title && (
        <h3 className="rec-title">
          <RecText text={item.title} />
        </h3>
      )}
      <p className="rec-message">
        <RecText text={item.message} />
      </p>
      {!!chips.length && !compact && (
        <div className="rec-why">
          {chips.map((chip) => (
            <span key={chip} className="pill">
              <RecText text={chip} />
            </span>
          ))}
        </div>
      )}
      {articles.length && !compact ? (
        <ul className="rec-articles">
          {articles.map((row) => (
            <li key={row.article}>
              <strong>{row.article}</strong>
              <PriceGapMeter
                clientAvg={row.clientAvgPrice}
                shipmentAvg={row.shipmentAvgPrice}
                gapPercent={row.gapPercent}
              />
            </li>
          ))}
        </ul>
      ) : null}
      {item.llm_comment ? (
        <div className="rec-llm arrive">
          <div className="rec-llm-label">Совет ИИ</div>
          <RecText text={item.llm_comment} />
        </div>
      ) : showWait ? (
        <div className="rec-llm wait" aria-hidden="true">
          <div className="rec-llm-label">Совет ИИ</div>
          <span className="rec-llm-ghost">Пишу, что сказать менеджеру…</span>
        </div>
      ) : null}
    </article>
  );
}
