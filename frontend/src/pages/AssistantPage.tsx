import { useEffect, useRef, useState } from "react";
import { api, formatMoney } from "../api";
import {
  ASSISTANT_CHIPS,
  assistantErrorText,
  historyPayload,
  rankChangeLabel,
  splitAnswer,
  type AssistantFactCard,
  type AssistantFollowUp,
  type AssistantReply,
  type ChatMessage,
} from "../assistant";
import AssistantWait from "../components/AssistantWait";
import PageHeader from "../components/PageHeader";

function newId(): string {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function AnswerBody({ text }: { text: string }) {
  return (
    <>
      {splitAnswer(text).map((part, index) => (
        <p key={`${index}-${part.slice(0, 12)}`} className="assistant-line" style={{ animationDelay: `${index * 80}ms` }}>
          {part}
        </p>
      ))}
    </>
  );
}

function FactCards({
  cards,
  onPrompt,
}: {
  cards: AssistantFactCard[];
  onPrompt: (prompt: string) => void;
}) {
  if (!cards.length) return null;
  return (
    <div className="assistant-facts">
      {cards.map((card) => (
        <section key={`${card.tool}-${card.title}`} className="assistant-fact-card">
          <header>
            <strong>{card.title}</strong>
            {card.period ? <span className="muted">{card.period}</span> : null}
          </header>
          <ol>
            {card.rows.map((row) => {
              const change = rankChangeLabel(row.rank_delta, row.prev_rank, row.is_new);
              const nums = [
                row.quantity != null ? `${formatMoney(row.quantity)} шт` : "",
                row.amount != null ? `${formatMoney(row.amount)} тг` : "",
                row.percent != null ? `${formatMoney(row.percent)}%` : "",
              ].filter(Boolean);
              const inner = (
                <span className="assistant-fact-row">
                  <span className="assistant-fact-rank">{row.rank}</span>
                  <span className="assistant-fact-copy">
                    <span className="assistant-fact-title">{row.title}</span>
                    {row.hint ? <span className="muted">{row.hint}</span> : null}
                  </span>
                  {change ? <span className="assistant-fact-delta">{change}</span> : null}
                  {nums.length ? <span className="assistant-fact-nums">{nums.join(" · ")}</span> : null}
                </span>
              );
              if (!row.prompt) {
                return <li key={`${row.rank}-${row.title}`}>{inner}</li>;
              }
              return (
                <li key={`${row.rank}-${row.title}`}>
                  <button type="button" onClick={() => onPrompt(row.prompt || "")}>
                    {inner}
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [messages, busy]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    const userMsg: ChatMessage = { id: newId(), role: "user", content: question };
    const next = [...messages, userMsg];
    setMessages(next);
    setDraft("");
    setError("");
    setBusy(true);
    try {
      const reply = await api<AssistantReply>("/api/v1/assistant/ask", {
        method: "POST",
        body: JSON.stringify({
          message: question,
          history: historyPayload(messages),
        }),
      });
      if (reply.status !== "ok" || !reply.answer.trim()) {
        const detail = assistantErrorText(reply);
        setMessages([
          ...next,
          {
            id: newId(),
            role: "assistant",
            content: detail,
            error: detail,
            tools: reply.tools,
            facts: reply.facts,
            followUps: reply.follow_ups,
          },
        ]);
        return;
      }
      setMessages([
        ...next,
        {
          id: newId(),
          role: "assistant",
          content: reply.answer,
          tools: reply.tools,
          facts: reply.facts,
          followUps: reply.follow_ups,
        },
      ]);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Не удалось получить ответ";
      setError(detail);
      setMessages([...next, { id: newId(), role: "assistant", content: detail, error: detail }]);
    } finally {
      setBusy(false);
    }
  }

  const last = messages[messages.length - 1];
  const followUps: AssistantFollowUp[] = !busy && last?.role === "assistant" ? last.followUps || [] : [];

  return (
    <>
      <PageHeader title="Ассистент" />
      <div className="assistant-layout panel">
        <div className="assistant-thread" role="log" aria-live="polite">
          {messages.length === 0 && !busy ? (
            <div className="assistant-empty-grid">
              {ASSISTANT_CHIPS.map((chip, index) => (
                <button
                  key={chip.label}
                  type="button"
                  className="assistant-prompt-card"
                  style={{ animationDelay: `${index * 70}ms` }}
                  onClick={() => send(chip.prompt)}
                >
                  <strong>{chip.label}</strong>
                  <span className="muted">{chip.prompt}</span>
                </button>
              ))}
            </div>
          ) : null}
          {messages.map((item) => (
            <article
              key={item.id}
              className={`assistant-bubble ${item.role}${item.error ? " is-error" : ""}`}
            >
              <span className="assistant-role">{item.role === "user" ? "Вы" : "Ассистент"}</span>
              {item.role === "assistant" ? <AnswerBody text={item.content} /> : <p>{item.content}</p>}
              {item.role === "assistant" && item.facts?.length ? (
                <FactCards cards={item.facts} onPrompt={(prompt) => send(prompt)} />
              ) : null}
              {!!item.tools?.length && (
                <p className="assistant-tools">
                  {item.tools.map((tool) => (
                    <span key={`${item.id}-${tool.name}-${tool.label}`} className="pill">
                      {tool.label}
                    </span>
                  ))}
                </p>
              )}
            </article>
          ))}
          {busy ? <AssistantWait /> : null}
          {followUps.length ? (
            <div className="assistant-follow">
              <span className="muted">Дальше</span>
              {followUps.map((item) => (
                <button key={item.prompt} type="button" className="btn ghost sm" onClick={() => send(item.prompt)}>
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}
          <div ref={bottom} />
        </div>
        {error ? <div className="alert">{error}</div> : null}
        <form
          className="assistant-form"
          onSubmit={(event) => {
            event.preventDefault();
            void send(draft);
          }}
        >
          <label className="field assistant-input">
            <span className="sr-only">Вопрос</span>
            <textarea
              rows={2}
              value={draft}
              disabled={busy}
              placeholder="Спросите по данным за текущий квартал…"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send(draft);
                }
              }}
            />
          </label>
          <button type="submit" className="btn" disabled={busy || !draft.trim()}>
            Спросить
          </button>
        </form>
      </div>
    </>
  );
}
