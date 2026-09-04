import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";

const CARDS = [
  {
    role: "Manager",
    path: "/uploads",
    points: [
      "Загрузка Excel: шаблон → заполнение → загрузка → errors.xlsx при ошибках",
      "Мотивация и оборачиваемость только по своим клиентам (после закрепления)",
    ],
  },
  {
    role: "Analytic",
    path: "/recommendations",
    points: [
      "Отчёты + Excel-экспорт",
      "Журнал 1С, справочники, рекомендации (правила + опционально LLM)",
    ],
  },
  {
    role: "Regional director",
    path: "/quarterly",
    points: ["Квартальные планы и итоговый отчёт", "Факт отгрузок"],
  },
  {
    role: "Admin",
    path: "/admin",
    points: [
      "Проверить связь с 1С и запустить синхронизацию",
      "Пользователи: создать менеджера, на контрагенте закрепить «свои клиенты»",
      "Журнал аудита, участники акции, LLM и рассылка (состав письма и SMTP)",
    ],
  },
];

export default function HelpPage() {
  return (
    <>
      <PageHeader
        title="Справка"
        subtitle="Что доступно в системе по ролям"
      />
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
