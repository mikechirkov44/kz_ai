import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import PageHeader from "../components/PageHeader";
import { defaultHelpTab, HELP_TABS, helpTabById, type HelpTabId } from "../helpContent";

export default function HelpPage() {
  const { me } = useAuth();
  const [picked, setPicked] = useState<HelpTabId | null>(null);
  const tab = picked ?? defaultHelpTab(me?.role);
  const current = helpTabById(tab);

  return (
    <>
      <PageHeader title="Справка" subtitle="Как работать с сервисом: ввод данных, отчёты, 1С и роли" />
      <div className="seg-tabs" role="tablist" aria-label="Разделы справки">
        {HELP_TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`seg-tab ${tab === item.id ? "active" : ""}`}
            onClick={() => setPicked(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p className="help-intro">{current.intro}</p>
      <div className="help-blocks">
        {current.blocks.map((block) => (
          <section key={block.title} className="panel help-card">
            <div className="help-card-head">
              <h2>{block.title}</h2>
              {block.path && (
                <Link className="help-link" to={block.path}>
                  {block.pathLabel || "Открыть"} →
                </Link>
              )}
            </div>
            {!!block.steps?.length && (
              <ol className="help-steps">
                {block.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            )}
            {!!block.notes?.length && (
              <ul className="help-notes">
                {block.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
    </>
  );
}
