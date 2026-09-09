import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  allowedQuickStartTools,
  defaultQuickStartPaths,
  QUICK_START_MAX,
  readQuickStartPaths,
  writeQuickStartPaths,
  resolveQuickStartTools,
} from "../quickStart";

type Props = {
  userId: string;
  role?: string | null;
};

export default function QuickStart({ userId, role }: Props) {
  const [paths, setPaths] = useState(() => readQuickStartPaths(userId, role));
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>(paths);

  useEffect(() => {
    const next = readQuickStartPaths(userId, role);
    setPaths(next);
    setDraft(next);
    setEditing(false);
  }, [userId, role]);

  const tools = resolveQuickStartTools(paths, role);
  const options = allowedQuickStartTools(role);

  function toggle(path: string) {
    setDraft((prev) => {
      if (prev.includes(path)) return prev.filter((item) => item !== path);
      if (prev.length >= QUICK_START_MAX) return prev;
      return [...prev, path];
    });
  }

  function save() {
    if (!draft.length) return;
    setPaths(writeQuickStartPaths(userId, draft, role));
    setEditing(false);
  }

  function reset() {
    const next = defaultQuickStartPaths(role);
    setDraft(next);
  }

  return (
    <div className="panel">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Быстрый старт</h2>
        {!editing ? (
          <button className="btn secondary sm" type="button" onClick={() => setEditing(true)}>
            Настроить
          </button>
        ) : (
          <div className="toolbar" style={{ gap: 8 }}>
            <button className="btn secondary sm" type="button" onClick={reset}>
              По роли
            </button>
            <button className="btn secondary sm" type="button" onClick={() => { setDraft(paths); setEditing(false); }}>
              Отмена
            </button>
            <button className="btn sm" type="button" disabled={!draft.length} onClick={save}>
              Сохранить
            </button>
          </div>
        )}
      </div>
      {editing ? (
        <>
          <p className="muted" style={{ margin: "8px 0 12px" }}>
            До {QUICK_START_MAX} пунктов из доступных вашей роли. Сейчас {draft.length}.
          </p>
          <div className="quick-start-options">
            {options.map((tool) => {
              const checked = draft.includes(tool.to);
              const blocked = !checked && draft.length >= QUICK_START_MAX;
              return (
                <label
                  key={tool.to}
                  className={`quick-start-chip${checked ? " is-on" : ""}${blocked ? " is-blocked" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={blocked}
                    onChange={() => toggle(tool.to)}
                  />
                  {tool.label}
                </label>
              );
            })}
          </div>
        </>
      ) : (
        <div className="toolbar" style={{ marginTop: 12 }}>
          {tools.map((tool) => (
            <Link key={tool.to} className="btn secondary" to={tool.to}>
              {tool.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
