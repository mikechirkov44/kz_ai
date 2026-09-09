import { systemHealthChips, type SystemHealthPayload } from "../systemHealth";

type Props = {
  health: SystemHealthPayload | null;
  error?: string;
};

export default function SystemHealth({ health, error }: Props) {
  const loading = !health && !error;
  const chips = !loading && !error ? systemHealthChips(health, true) : [];

  return (
    <div className="stat stat-health">
      <div className="label">Состояние системы</div>
      {loading ? (
        <p className="health-status-msg muted">Проверяю…</p>
      ) : error ? (
        <p className="health-status-msg">{error}</p>
      ) : (
        <ul className="health-chips">
          {chips.map((chip) => (
            <li key={chip.key} className={`health-chip ${chip.tone}`}>
              <span className="health-dot" aria-hidden />
              <span className="health-chip-name">{chip.name}</span>
              <span className="health-chip-status">{chip.statusLabel}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
