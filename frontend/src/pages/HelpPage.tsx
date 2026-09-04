import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";

const CARDS = [
  {
    role: "Manager",
    path: "/uploads",
    points: [
      "Загрузка Excel: шаблон → заполнение → загрузка → errors.xlsx при ошибках",
      "Мотивация и оборачиваемость по акционным клиентам",
    ],
  },
  {
    role: "Analytic",
    path: "/recommendations",
    points: [
      "Отчёты + Excel-экспорт",
      "Журнал 1С, справочники, рекомендации",
    ],
  },
  {
    role: "Regional director",
    path: "/quarterly",
    points: ["Квартальные планы и §5.4", "Факт отгрузок, digest через админа"],
  },
  {
    role: "Admin",
    path: "/admin",
    points: [
      "OData: проверить связь → инкремент / полный sync",
      "Полный sync нужен для производства (с 2025) и заказов",
      "Флаг is_promo у участников акции",
    ],
  },
];

export default function HelpPage() {
  return (
    <>
      <PageHeader
        title="Справка"
        subtitle="Краткие гайды по ролям. Полные тексты — в репозитории docs/guides/"
      />
      <div className="hint-banner" style={{ marginBottom: 16 }}>
        Операции Docker / SMTP / rate limit — см. <code>docs/runbook.md</code>. Приёмка —{" "}
        <code>docs/acceptance.md</code> и шаблон <code>docs/uat-results.md</code>.
      </div>
      <div className="grid-2">
        {CARDS.map((c) => (
          <div key={c.role} className="panel">
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
              <h2 style={{ margin: 0 }}>{c.role}</h2>
              <Link className="help-link" to={c.path}>
                Открыть →
              </Link>
            </div>
            <ul className="dash-list">
              {c.points.map((p) => (
                <li key={p}>
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </>
  );
}
