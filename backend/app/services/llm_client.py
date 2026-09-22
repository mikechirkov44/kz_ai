"""OpenAI-compatible chat client for recommendation enrichment."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from app.domain.llm_enrich import (
    COMMENT_BATCH_SIZE,
    MAX_ENRICH_ITEMS,
    apply_llm_comments,
    build_comment_enrich_messages,
    build_llm_digest,
    build_report_enrich_messages,
    chat_completions_url,
    llm_report_is_useful,
    parse_llm_comments,
    parse_llm_report,
    parse_llm_summary,
    slice_for_enrichment,
)
from app.schemas import RecommendationItem, RecommendationsResponse
from app.services.llm_settings import LlmConfig, get_llm_config
from app.services.openrouter_catalog import looks_like_openrouter

logger = logging.getLogger(__name__)

PING_USER_MESSAGE = "Ответь одним словом: ok"
ENRICH_TIMEOUT_FLOOR = 60.0
MAX_COMPLETION_TOKENS = 400
_AFFORD_TOKENS_RE = re.compile(r"can only afford\s+(\d+)", re.I)


def comment_max_tokens(_item_count: int, budget: int = MAX_COMPLETION_TOKENS) -> int:
    return max(16, int(budget))


def affordable_max_tokens(detail: str, requested: int) -> Optional[int]:
    match = _AFFORD_TOKENS_RE.search(detail or "")
    if not match:
        return None
    afford = int(match.group(1))
    if afford < 16 or afford >= requested:
        return None
    return afford


def _provider_error_text(text: str) -> str:
    raw = (text or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.replace("\n", " ")
    if not isinstance(data, dict):
        return raw.replace("\n", " ")
    err = data.get("error")
    if isinstance(err, dict) and isinstance(err.get("message"), str) and err["message"].strip():
        return err["message"].strip()
    if isinstance(data.get("message"), str) and data["message"].strip():
        return data["message"].strip()
    return raw.replace("\n", " ")


def _http_error_message(status: int, text: str, *, model: str = "", base_url: str = "") -> str:
    detail = _provider_error_text(text)
    if status == 401:
        short = detail[:180]
        return "Ключ API отклонён — проверьте ключ в кабинете провайдера" + (f": {short}" if short else "")
    ident = (model or "").strip().lower()
    openrouter_error = (
        looks_like_openrouter(base_url)
        or ident.endswith(":free")
        or ident.startswith("openrouter")
        or "openrouter.ai" in detail.lower()
        or "never purchased" in detail.lower()
    )
    if status == 402 and not openrouter_error:
        short = detail[:180]
        return "HTTP 402" + (f": {short}" if short else "")
    if status == 402:
        ident = (model or "").strip().lower()
        is_free = ident.endswith(":free") or ident in {"openrouter/free", "openrouter/auto"}
        lower = detail.lower()
        if "never purchased" in lower or "insufficient credits" in lower:
            if is_free:
                return (
                    "OpenRouter отклонил запрос: нет предоплаченных кредитов или баланс отрицательный. "
                    "Кредитная линия в кабинете не заменяет пополнение Credits. "
                    "openrouter.ai/settings/credits"
                )
            return (
                "Эта модель платная (нужны кредиты). Для пробы без списания выберите Free — id оканчивается на :free. "
                "Кредитная линия OpenRouter для API не всегда действует. openrouter.ai/settings/credits"
            )
        afford = None
        match = _AFFORD_TOKENS_RE.search(detail)
        if match:
            afford = int(match.group(1))
        if afford:
            return f"Недостаточно кредитов OpenRouter (доступно {afford} токенов ответа)"
        return "Недостаточно кредитов OpenRouter — пополните счёт"
    short = detail[:180]
    return f"HTTP {status}" + (f": {short}" if short else "")


def enrich_timeout(config: LlmConfig) -> float:
    return max(float(config.timeout_seconds or 0), ENRICH_TIMEOUT_FLOOR)


def _auth_headers(api_key: str, *, openrouter: bool = False) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if openrouter:
        headers["HTTP-Referer"] = "https://github.com/mikechirkov44/kz_ai"
        headers["X-Title"] = "AI Jewelry Analytics"
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
        return http.post(
            url,
            headers=_auth_headers(api_key, openrouter="openrouter.ai" in (url or "").lower()),
            json=payload,
        )
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
    extra = message.get("reasoning_content") or message.get("reasoning")
    extra_text = extra.strip() if isinstance(extra, str) else ""
    content = message.get("content")
    body = ""
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str) and part.strip():
                parts.append(part.strip())
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        body = "\n".join(parts).strip()
    elif isinstance(content, str) and content.strip():
        body = content.strip()
    if body and extra_text and extra_text not in body:
        return f"{body}\n{extra_text}"
    return body or extra_text


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
        return {
            "status": "error",
            "detail": _http_error_message(
                response.status_code,
                response.text,
                model=config.model,
                base_url=config.base_url,
            ),
        }
    content = _choice_content(response.json())
    if not content:
        return {"status": "error", "detail": "Пустой ответ модели"}
    return {"status": "ok", "detail": content}


def _chat_content(
    url: str,
    config: LlmConfig,
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    http: httpx.Client,
    timeout: Optional[float] = None,
) -> tuple[str, str]:
    wait = float(timeout) if timeout is not None else float(config.timeout_seconds)
    tokens = max(16, int(max_tokens))
    last_error = ""
    for _attempt in range(2):
        payload = {
            "model": config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": tokens,
        }
        try:
            response = _post_chat(
                url,
                api_key=config.api_key,
                payload=payload,
                timeout=wait,
                client=http,
            )
        except httpx.TimeoutException:
            logger.warning("LLM chat timeout")
            return "", "Таймаут модели"
        except httpx.HTTPError as exc:
            logger.warning("LLM chat failed: %s", exc)
            return "", str(exc)[:200]
        if response.status_code == 402:
            last_error = _http_error_message(402, response.text, model=config.model, base_url=config.base_url)
            retry_tokens = affordable_max_tokens(response.text or "", tokens)
            logger.warning("LLM chat HTTP 402 %s", last_error)
            if retry_tokens:
                tokens = retry_tokens
                continue
            return "", last_error
        if response.status_code >= 400:
            last_error = _http_error_message(
                response.status_code, response.text, model=config.model, base_url=config.base_url
            )
            logger.warning("LLM chat %s", last_error)
            return "", last_error
        try:
            content = _choice_content(response.json())
        except ValueError:
            logger.warning("LLM chat: response is not JSON")
            return "", "Ответ API не JSON"
        if not content:
            return "", "Пустой ответ модели"
        return content, ""
    return "", last_error or "Недостаточно кредитов OpenRouter — пополните счёт"


def complete_chat(
    config: LlmConfig,
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
    client: Optional[httpx.Client] = None,
) -> tuple[str, str]:
    url = chat_completions_url(config.base_url)
    if not url:
        return "", "Не указан адрес API модели"
    own = client is None
    wait = enrich_timeout(config)
    http = client or httpx.Client(timeout=wait)
    try:
        return _chat_content(
            url,
            config,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            http=http,
            timeout=wait,
        )
    finally:
        if own:
            http.close()


def enrich_recommendation_items(
    items: list[RecommendationItem],
    config: LlmConfig,
    *,
    client: Optional[httpx.Client] = None,
) -> tuple[list[RecommendationItem], str, Optional[str], Optional[dict], Optional[str]]:
    if not items:
        return items, "ok", None, None, None
    raw = [item.model_dump() for item in items]
    subset = slice_for_enrichment(raw, MAX_ENRICH_ITEMS)
    url = chat_completions_url(config.base_url)
    if not url:
        return items, "error", None, None, "Не указан адрес API модели"
    digest = build_llm_digest(raw)
    comments: list[Optional[str]] = [None] * len(subset)
    summary: Optional[str] = None
    report: Optional[dict] = None
    last_error = ""
    own = client is None
    wait = enrich_timeout(config)
    http = client or httpx.Client(timeout=wait)
    try:
        report_raw, err = _chat_content(
            url,
            config,
            build_report_enrich_messages(digest),
            max_tokens=MAX_COMPLETION_TOKENS,
            temperature=0.2,
            http=http,
            timeout=wait,
        )
        if err:
            last_error = err
        if report_raw:
            summary = parse_llm_summary(report_raw)
            parsed_report = parse_llm_report(report_raw)
            if llm_report_is_useful(parsed_report):
                report = parsed_report
            if not summary and report:
                summary = str(report.get("situation") or report.get("headline") or "").strip() or None
        step = max(COMMENT_BATCH_SIZE, 1)
        for start in range(0, len(subset), step):
            chunk = subset[start : start + step]
            content, err = _chat_content(
                url,
                config,
                build_comment_enrich_messages(chunk),
                max_tokens=comment_max_tokens(len(chunk)),
                temperature=0.35,
                http=http,
                timeout=wait,
            )
            parsed = parse_llm_comments(content, len(chunk))
            if not any(parsed):
                last_error = err or "Модель не вернула советы"
                logger.warning("LLM comment enrich empty parse: %s", (content or "")[:400])
                continue
            for offset, text in enumerate(parsed):
                comments[start + offset] = text
    finally:
        if own:
            http.close()
    if not any(comments) and not summary and not report:
        return items, "error", None, None, last_error or "Модель не вернула советы"
    enriched_raw = apply_llm_comments(raw, comments)
    enriched = [RecommendationItem(**row) for row in enriched_raw]
    return enriched, "ok", summary, report, None


def maybe_enrich_recommendations(
    db,
    report: RecommendationsResponse,
    *,
    client: Optional[httpx.Client] = None,
) -> RecommendationsResponse:
    config = get_llm_config(db)
    report.llm_error = None
    if not config.enabled:
        report.llm_status = "off"
        return report
    if not config.base_url:
        report.llm_status = "error"
        report.llm_error = "Не указан адрес API модели"
        return report
    try:
        items, status, summary, llm_report, error = enrich_recommendation_items(
            report.items, config, client=client
        )
        report.items = items
        report.llm_status = status
        report.llm_error = error
        if summary:
            report.summary = summary
        if llm_report:
            report.llm_report = llm_report
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM enrichment crashed")
        report.llm_status = "error"
        report.llm_error = str(exc)[:300]
    return report
