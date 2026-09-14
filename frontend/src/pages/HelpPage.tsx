import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import NavIcon, { iconForPath } from "../components/NavIcon";
import PageHeader from "../components/PageHeader";
import {
  defaultHelpTab,
  HELP_TABS,
  helpTabById,
  searchHelp,
  type HelpBlock,
  type HelpTabId,
} from "../helpContent";

export default function HelpPage() {
  const { me } = useAuth();
  const [picked, setPicked] = useState<HelpTabId | null>(null);
  const [query, setQuery] = useState("");
  const tab = picked ?? defaultHelpTab(me?.role);
  const current = helpTabById(tab);
  const searching = query.trim().length >= 2;
  const hits = useMemo(() => (searching ? searchHelp(query) : []), [query, searching]);

  return (
    <>
      <PageHeader title="Справка" subtitle="Как работать в сервисе: цифры, экраны и роли" />

      <div className="help-top">
        <div className="seg-tabs" role="tablist" aria-label="Разделы справки">
          {HELP_TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={!searching && tab === item.id}
              className={`seg-tab ${!searching && tab === item.id ? "active" : ""}`}
              onClick={() => {
                setPicked(item.id);
                setQuery("");
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        <label className="help-search">
          <span className="sr-only">Поиск по справке</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Найти в справке…"
            autoComplete="off"
          />
        </label>
      </div>

      {searching ? (
        <>
          <p className="help-intro">
            {hits.length
              ? `Найдено разделов: ${hits.length}`
              : `Ничего не нашлось по запросу «${query.trim()}». Попробуйте другое слово.`}
          </p>
          <div className="help-blocks">
            {hits.map((hit) => (
              <HelpCard
                key={`${hit.tabId}-${hit.block.title}`}
                block={hit.block}
                badge={hit.tabLabel}
                onOpenTab={() => {
                  setPicked(hit.tabId);
                  setQuery("");
                }}
              />
            ))}
          </div>
        </>
      ) : (
        <>
          {current.intro ? <p className="help-intro">{current.intro}</p> : null}
          <div className="help-blocks">
            {current.blocks.map((block) => (
              <HelpCard key={block.title} block={block} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

function HelpCard({
  block,
  badge,
  onOpenTab,
}: {
  block: HelpBlock;
  badge?: string;
  onOpenTab?: () => void;
}) {
  const icon = block.path ? iconForPath(block.path) : undefined;
  return (
    <section className="panel help-card">
      <div className="help-card-head">
        <div className="help-card-title">
          {icon ? (
            <span className="help-card-icon">
              <NavIcon name={icon} size={18} />
            </span>
          ) : null}
          <div>
            {badge ? (
              <button type="button" className="help-badge" onClick={onOpenTab}>
                {badge}
              </button>
            ) : null}
            <h2>{block.title}</h2>
          </div>
        </div>
        {block.path && (
          <Link className="help-link" to={block.path}>
            {block.pathLabel || "Открыть"} →
          </Link>
        )}
      </div>
      {block.lead && <p className="help-lead">{block.lead}</p>}
      {!!block.steps?.length && (
        <ol className="help-steps">
          {block.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      )}
      {!!block.notes?.length && (
        <div className="help-callout">
          <div className="help-callout-label">На заметку</div>
          <ul className="help-notes">
            {block.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
