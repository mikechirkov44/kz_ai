import RecText from "./RecText";
import { recActionLabel, type RecAction, type Recommendation } from "../recommendations";
import { buildExecutiveReport } from "../executiveReport";

export type LlmReport = {
  headline?: string;
  situation?: string;
  notes?: Record<string, string>;
};

type Props = {
  summary: string;
  items: Recommendation[];
  llmReport?: LlmReport | null;
};

const ACTION_ORDER: RecAction[] = ["return", "restock", "transfer", "reprice"];

export default function ExecutiveReport({ summary, items, llmReport }: Props) {
  const report = buildExecutiveReport(items);
  const notes = llmReport?.notes || {};
  const lead = llmReport?.situation || llmReport?.headline || summary;
  return (
    <div className="exec-report">
      {lead ? (
        <section className="exec-lead">
          {llmReport?.headline ? <div className="exec-lead-kicker">{llmReport.headline}</div> : null}
          <p>
            <RecText text={lead} />
          </p>
        </section>
      ) : null}

      <section className="exec-block">
        <h3>Обстановка</h3>
        {notes.focus ? (
          <p className="exec-note">
            <RecText text={notes.focus} />
          </p>
        ) : null}
        <div className="exec-kpis">
          <div className="exec-kpi">
            <strong>{report.total}</strong>
            <span>сигналов</span>
          </div>
          <div className="exec-kpi">
            <strong>{report.clients}</strong>
            <span>клиентов</span>
          </div>
          <div className="exec-kpi urgent">
            <strong>{report.severity.high}</strong>
            <span>срочно</span>
          </div>
          <div className="exec-kpi">
            <strong>{report.severity.medium}</strong>
            <span>важно</span>
          </div>
          <div className="exec-kpi">
            <strong>{report.severity.info}</strong>
            <span>на заметку</span>
          </div>
        </div>
        <div className="exec-actions">
          {ACTION_ORDER.map((action) => (
            <span key={action} className={`exec-action-chip tone-${action} ${report.actions[action] ? "" : "is-empty"}`}>
              <strong>{report.actions[action]}</strong>
              {recActionLabel(action)}
            </span>
          ))}
        </div>
      </section>

      <div className="exec-grid">
        {report.blocks.map((block) => (
          <section key={block.action} className={`exec-card tone-${block.action} ${block.count ? "" : "is-empty"}`}>
            <h3>
              {block.label}
              <span>{block.count}</span>
            </h3>
            {notes[block.action] ? (
              <p className="exec-note">
                <RecText text={notes[block.action]} />
              </p>
            ) : null}
            {block.count === 0 ? (
              <p className="muted">{block.empty}</p>
            ) : (
              <>
                <div className="exec-facts">
                  {block.facts.map((fact) => (
                    <div key={fact.label} className="exec-fact">
                      <span>{fact.label}</span>
                      <strong>
                        <RecText text={fact.value} />
                      </strong>
                    </div>
                  ))}
                </div>
                {block.top.length ? (
                  <ul className="exec-top">
                    {block.top.map((row) => (
                      <li key={`${row.counterparty}-${row.title}-${row.metric}`}>
                        <div>
                          <strong>{row.counterparty}</strong>
                          <span>
                            <RecText text={row.title} />
                          </span>
                        </div>
                        {row.metric ? (
                          <em>
                            <RecText text={row.metric} />
                          </em>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            )}
          </section>
        ))}
      </div>

      <section className="exec-block">
        <h3>Клиенты в фокусе</h3>
        {report.focus.length ? (
          <div className="exec-table-wrap">
            <table className="exec-table">
              <thead>
                <tr>
                  <th>Клиент</th>
                  <th>Сигналов</th>
                  <th>Действия</th>
                  <th>Главный кейс</th>
                </tr>
              </thead>
              <tbody>
                {report.focus.map((row) => (
                  <tr key={row.counterparty}>
                    <td>{row.counterparty}</td>
                    <td>{row.signals}</td>
                    <td>{row.actions.join(", ") || "—"}</td>
                    <td>
                      <RecText text={row.title} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">Клиентов в отчёте нет.</p>
        )}
      </section>
    </div>
  );
}
