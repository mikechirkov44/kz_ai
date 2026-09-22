import { useWaitTick } from "./AiBriefing";
import { ASSISTANT_WAIT_STEPS } from "../assistant";

export default function AssistantWait({ steps = ASSISTANT_WAIT_STEPS }: { steps?: readonly string[] }) {
  const tick = useWaitTick(true, 1400);
  const list = steps.length ? steps : ASSISTANT_WAIT_STEPS;
  const phrase = list[Math.abs(tick) % list.length];
  return (
    <div className="assistant-wait ai-brief thinking enchanting" aria-busy="true" aria-live="polite">
      <div className="ai-brief-orb live" aria-hidden="true">
        <span className="ai-brief-ring" />
        <span className="ai-brief-ring" />
        <span className="ai-brief-ring" />
        <span className="ai-brief-spark" />
        <span className="ai-brief-spark rev" />
        <span className="ai-brief-mote" />
        <span className="ai-brief-mote" />
        <span className="ai-brief-mote" />
        <span className="ai-brief-core" />
      </div>
      <div className="ai-brief-body">
        <strong>Смотрю данные</strong>
        <p>
          {phrase}
          <span className="ai-dots" aria-hidden>
            <i />
            <i />
            <i />
          </span>
        </p>
      </div>
    </div>
  );
}
