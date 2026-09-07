import { llmStatusLabel } from "../recommendations";

type Props = {
  summary?: string;
  llmStatus: string;
  thinking?: boolean;
  count?: number;
};

export default function AiBriefing({ summary = "", llmStatus, thinking = false, count = 0 }: Props) {
  const showModel = !thinking && llmStatus === "ok";
  const text = !thinking && showModel ? summary : "";
  return (
    <section className={`ai-brief ${thinking ? "thinking" : ""}`} aria-live="polite">
      <div className="ai-brief-orb" aria-hidden="true">
        <span className="ai-brief-ring" />
        <span className="ai-brief-ring" />
        <span className="ai-brief-core" />
      </div>
      <div className="ai-brief-body">
        <div className="ai-brief-meta">
          <h2>Ассистент по акции</h2>
          {thinking && (
            <span className="ai-brief-status">
              Анализирую
              <span className="ai-dots">
                <i />
                <i />
                <i />
              </span>
            </span>
          )}
          {showModel && <span className="ai-brief-status ok">{llmStatusLabel("ok")}</span>}
          {!thinking && count > 0 && <span className="muted">{count}</span>}
        </div>
        {text ? <p>{text}</p> : null}
      </div>
    </section>
  );
}
