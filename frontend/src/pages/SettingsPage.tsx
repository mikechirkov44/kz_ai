import { useState } from "react";
import PageHeader from "../components/PageHeader";
import { applyTheme, readTheme, THEMES, type ThemeId } from "../theme";

export default function SettingsPage() {
  const [theme, setTheme] = useState<ThemeId>(readTheme);

  function pick(id: ThemeId) {
    setTheme(applyTheme(id));
  }

  return (
    <>
      <PageHeader
        title="Настройки"
        subtitle="Цветовая схема только для этого браузера. На отчёты и данные не влияет."
      />
      <div className="panel">
        <h2>Оформление</h2>
        <p className="muted">Выберите схему. Изменение применяется сразу.</p>
        <div className="theme-grid">
          {THEMES.map((item) => {
            const active = theme === item.id;
            return (
              <button
                key={item.id}
                type="button"
                className={`theme-card ${active ? "active" : ""}`}
                onClick={() => pick(item.id)}
                aria-pressed={active}
              >
                <div className="theme-preview" aria-hidden>
                  <span style={{ background: item.swatches[0] }} />
                  <span style={{ background: item.swatches[1] }} />
                  <span style={{ background: item.swatches[2] }} />
                </div>
                <strong>{item.title}</strong>
                <span className="muted">{item.hint}</span>
                {active && <span className="pill ok">Выбрана</span>}
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}
