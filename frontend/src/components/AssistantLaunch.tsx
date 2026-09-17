import { NavLink } from "react-router-dom";

export default function AssistantLaunch() {
  return (
    <NavLink
      to="/assistant"
      title="Ассистент"
      className={({ isActive }) => `assistant-launch${isActive ? " active" : ""}`}
    >
      <span className="assistant-launch-orb ai-brief-orb live" aria-hidden>
        <span className="ai-brief-ring" />
        <span className="ai-brief-ring" />
        <span className="ai-brief-spark" />
        <span className="ai-brief-core" />
      </span>
      <span className="assistant-launch-label">Ассистент</span>
    </NavLink>
  );
}
