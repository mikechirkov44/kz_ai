"""OpenAI-compatible chat client for recommendation enrichment."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.domain.llm_enrich import (
    MAX_ENRICH_ITEMS,
    apply_llm_comments,
    build_enrich_messages,
    build_llm_digest,
    chat_completions_url,
    parse_llm_comments,
    parse_llm_report,
    parse_llm_summary,
    slice_for_enrichment,
)
from app.schemas import RecommendationItem, RecommendationsResponse
from app.services.llm_settings import LlmConfig, get_llm_config

logger = logging.getLogger(__name__)

PING_USER_MESSAGE = "Ответь одним словом: ok"


def _auth_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _post_chat(
    url: str,
    *,
    api_key: str,
    payload: dict,
    timeout: float,
    client: Optional[httpx.Client] = None,
) -> httpx.Response:
    own = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        return http.post(url, headers=_auth_headers(api_key), json=payload)
    finally:
        if own:
            http.close()


def _choice_content(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") or {}
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def check_llm_connection(config: LlmConfig, *, client: Optional[httpx.Client] = None) -> dict:
    url = chat_completions_url(config.base_url)
    if not url:
        return {"status": "error", "detail": "Не указан адрес API"}
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": PING_USER_MESSAGE}],
        "max_tokens": 8,
        "temperature": 0,
    }
    try:
        response = _post_chat(
            url,
            api_key=config.api_key,
            payload=payload,
            timeout=float(config.timeout_seconds),
            client=client,
        )
    except httpx.HTTPError as exc:
        logger.warning("LLM test failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
    if response.status_code >= 400:
        detail = (response.text or "")[:400] or f"HTTP {response.status_code}"
        return {"status": "error", "detail": detail}
    content = _choice_content(response.json())
    if not content:
        return {"status": "error", "detail": "Пустой ответ модели"}
    return {"status": "ok", "detail": content}


def enrich_recommendation_items(
    items: list[RecommendationItem],
    config: LlmConfig,
    *,
    client: Optional[httpx.Client] = None,
) -> tuple[list[RecommendationItem], str, Optional[str], Optional[dict]]:
    if not items:
        return items, "ok", None, None
    raw = [item.model_dump() for item in items]
    subset = slice_for_enrichment(raw, MAX_ENRICH_ITEMS)
    url = chat_completions_url(config.base_url)
    if not url:
        return items, "error", None, None
    payload = {
        "model": config.model,
        "messages": build_enrich_messages(subset, build_llm_digest(raw)),
        "temperature": 0.2,
        "max_tokens": min(5000, max(400, 90 * len(subset))),
    }
    try:
        response = _post_chat(
            url,
            api_key=config.api_key,
            payload=payload,
            timeout=float(config.timeout_seconds),
            client=client,
        )
    except httpx.HTTPError as exc:
        logger.warning("LLM enrich failed: %s", exc)
        return items, "error", None, None
    if response.status_code >= 400:
        logger.warning("LLM enrich HTTP %s", response.status_code)
        return items, "error", None, None
    try:
        content = _choice_content(response.json())
    except ValueError:
        return items, "error", None, None
    comments = parse_llm_comments(content, len(subset))
    if not any(comments):
        return items, "error", None, None
    enriched_raw = apply_llm_comments(raw, comments)
    enriched = [RecommendationItem(**row) for row in enriched_raw]
    return enriched, "ok", parse_llm_summary(content), parse_llm_report(content)


def maybe_enrich_recommendations(
    db,
    report: RecommendationsResponse,
    *,
    client: Optional[httpx.Client] = None,
) -> RecommendationsResponse:
    config = get_llm_config(db)
    if not config.enabled:
        report.llm_status = "off"
        return report
    if not config.base_url:
        report.llm_status = "error"
        return report
    try:
        items, status, summary, llm_report = enrich_recommendation_items(report.items, config, client=client)
        report.items = items
        report.llm_status = status
        if summary:
            report.summary = summary
        if llm_report:
            report.llm_report = llm_report
    except Exception:  # noqa: BLE001
        logger.exception("LLM enrichment crashed")
        report.llm_status = "error"
    return report
