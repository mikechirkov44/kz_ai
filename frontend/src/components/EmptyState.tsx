import { Link } from "react-router-dom";

type Props = {
  title: string;
  hint?: string;
  action?: { to: string; label: string };
};

export default function EmptyState({ title, hint, action }: Props) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      {hint ? <p>{hint}</p> : null}
      {action ? (
        <Link className="btn secondary" to={action.to}>
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}
