"""Run a scoped data-assistant turn: plan tools, fetch facts, answer."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.domain.assistant import (
    ANSWER_MAX_TOKENS,
    MAX_QUESTION,
    PLAN_MAX_TOKENS,
    TOOL_LABELS,
    build_answer_messages,
    build_plan_messages,
    current_year_quarter,
    expand_plan,
    fact_cards,
    fallback_plan,
    follow_ups_from_facts,
    parse_plan,
    sanitize_history,
    template_answer,
)
from app.models import User
from app.services.assistant_query import run_tool
from app.services.llm_client import complete_chat
from app.services.llm_settings import get_llm_config

logger = logging.getLogger(__name__)


def _collect_facts(db: Session, user: User, calls: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    facts: list[dict[str, Any]] = []
    used: list[dict[str, str]] = []
    for call in calls:
        try:
            payload = run_tool(db, user, call["name"], call["args"])
        except Exception:  # noqa: BLE001
            logger.exception("assistant tool %s failed", call["name"])
            payload = {"tool": call["name"], "error": "Не удалось прочитать данные"}
        facts.append(payload)
        used.append({"name": call["name"], "label": TOOL_LABELS.get(call["name"], call["name"])})
    return facts, used


def _pack(
    *,
    status: str,
    answer: str,
    error: Optional[str],
    facts: list[dict[str, Any]],
    used: list[dict[str, str]],
    year: int,
    quarter: int,
) -> dict[str, Any]:
    return {
        "status": status,
        "answer": answer,
        "error": error,
        "tools": used,
        "facts": fact_cards(facts),
        "follow_ups": follow_ups_from_facts(facts),
        "period": {"year": year, "quarter": quarter},
    }


def ask_assistant(
    db: Session,
    user: User,
    message: str,
    history: Optional[list[dict[str, Any]]] = None,
    *,
    today: Optional[date] = None,
    client: Optional[httpx.Client] = None,
) -> dict[str, Any]:
    question = (message or "").strip()[:MAX_QUESTION]
    year, quarter = current_year_quarter(today or date.today())
    turns = sanitize_history(history)
    empty = _pack(status="error", answer="", error="Напишите вопрос", facts=[], used=[], year=year, quarter=quarter)
    if not question:
        return empty

    config = get_llm_config(db)
    calls: list[dict[str, Any]] = []
    plan_error = ""
    if config.enabled:
        plan_raw, plan_error = complete_chat(
            config,
            build_plan_messages(question, year=year, quarter=quarter, history=turns),
            max_tokens=PLAN_MAX_TOKENS,
            temperature=0.1,
            client=client,
        )
        calls = parse_plan(plan_raw, year=year, quarter=quarter)
        if not calls:
            calls = fallback_plan(question, year=year, quarter=quarter)
            if plan_error:
                logger.info("assistant plan fallback: %s", plan_error)
    else:
        calls = fallback_plan(question, year=year, quarter=quarter)

    calls = expand_plan(calls, question=question, year=year, quarter=quarter)
    facts, used = _collect_facts(db, user, calls)

    if not config.enabled:
        return _pack(
            status="ok",
            answer=template_answer(facts),
            error=None,
            facts=facts,
            used=used,
            year=year,
            quarter=quarter,
        )

    answer, answer_error = complete_chat(
        config,
        build_answer_messages(question, facts, year=year, quarter=quarter, history=turns),
        max_tokens=ANSWER_MAX_TOKENS,
        temperature=0.25,
        client=client,
    )
    if not (answer or "").strip():
        return _pack(
            status="ok" if fact_cards(facts) else "error",
            answer=template_answer(facts) if fact_cards(facts) else "",
            error=None if fact_cards(facts) else (answer_error or plan_error or "Модель не ответила"),
            facts=facts,
            used=used,
            year=year,
            quarter=quarter,
        )
    return _pack(
        status="ok",
        answer=answer.strip(),
        error=None,
        facts=facts,
        used=used,
        year=year,
        quarter=quarter,
    )
