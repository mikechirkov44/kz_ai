"""Admin LLM settings: encrypted API key, OpenAI-compatible endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LlmSettings
from app.security import decrypt_secret, encrypt_secret
from app.services.openai_catalog import OPENAI_BASE_URL, OPENAI_DEFAULT_MODEL, looks_like_openai
from app.services.openrouter_catalog import looks_like_openrouter

DEFAULT_SLUG = "default"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openrouter/free"
PROVIDER_OPENAI = "openai"
PROVIDER_OPENROUTER = "openrouter"
DEFAULT_TIMEOUT = 20
DEFAULT_ADVICE_STYLE = "standard"
ADVICE_STYLES = ("economy", "standard", "detailed")
ADVICE_STYLE_TOKENS = {
    "economy": 250,
    "standard": 500,
    "detailed": 1200,
}
ADVICE_STYLE_BATCH = {
    "economy": 4,
    "standard": 4,
    "detailed": 3,
}


def normalize_provider(provider: Optional[str], base_url: str = "") -> str:
    value = (provider or "").strip().lower()
    if value == PROVIDER_OPENAI:
        return PROVIDER_OPENAI
    if value == PROVIDER_OPENROUTER:
        return PROVIDER_OPENROUTER
    if looks_like_openai(base_url) and not looks_like_openrouter(base_url):
        return PROVIDER_OPENAI
    return PROVIDER_OPENROUTER


def provider_defaults(provider: str) -> tuple[str, str]:
    if normalize_provider(provider) == PROVIDER_OPENAI:
        return OPENAI_BASE_URL, OPENAI_DEFAULT_MODEL
    return DEFAULT_BASE_URL, DEFAULT_MODEL


def normalize_advice_style(raw: Optional[str]) -> str:
    value = (raw or "").strip().lower()
    if value in ADVICE_STYLES:
        return value
    return DEFAULT_ADVICE_STYLE


def advice_style_tokens(raw: Optional[str]) -> int:
    return ADVICE_STYLE_TOKENS[normalize_advice_style(raw)]


def advice_style_batch(raw: Optional[str]) -> int:
    return ADVICE_STYLE_BATCH[normalize_advice_style(raw)]


@dataclass(frozen=True)
class LlmConfig:
    enabled: bool
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int
    advice_style: str = DEFAULT_ADVICE_STYLE


def ensure_llm_settings(db: Session) -> LlmSettings:
    row = db.scalar(select(LlmSettings).where(LlmSettings.slug == DEFAULT_SLUG))
    if row:
        return row
    row = LlmSettings(
        slug=DEFAULT_SLUG,
        enabled=False,
        provider="openai_compatible",
        base_url=DEFAULT_BASE_URL,
        model=DEFAULT_MODEL,
        api_key_encrypted="",
        timeout_seconds=DEFAULT_TIMEOUT,
        advice_style=DEFAULT_ADVICE_STYLE,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_llm_row(db: Session) -> LlmSettings:
    return ensure_llm_settings(db)


def settings_public_view(row: LlmSettings) -> dict:
    base_url = row.base_url or ""
    return {
        "enabled": bool(row.enabled),
        "provider": normalize_provider(row.provider, base_url),
        "base_url": base_url,
        "model": row.model or DEFAULT_MODEL,
        "api_key_set": bool(row.api_key_encrypted),
        "timeout_seconds": int(row.timeout_seconds or DEFAULT_TIMEOUT),
        "advice_style": normalize_advice_style(getattr(row, "advice_style", None)),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_llm_config(db: Session) -> LlmConfig:
    row = get_llm_row(db)
    api_key = decrypt_secret(row.api_key_encrypted) if row.api_key_encrypted else ""
    return LlmConfig(
        enabled=bool(row.enabled),
        base_url=(row.base_url or "").strip(),
        model=(row.model or DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        api_key=api_key,
        timeout_seconds=int(row.timeout_seconds or DEFAULT_TIMEOUT),
        advice_style=normalize_advice_style(getattr(row, "advice_style", None)),
    )


def upsert_llm_settings(
    db: Session,
    *,
    enabled: bool,
    base_url: str,
    model: str,
    api_key: Optional[str],
    timeout_seconds: int,
    advice_style: str = DEFAULT_ADVICE_STYLE,
    provider: Optional[str] = None,
) -> LlmSettings:
    row = get_llm_row(db)
    row.enabled = enabled
    chosen = normalize_provider(provider if provider is not None else row.provider, base_url)
    default_url, default_model = provider_defaults(chosen)
    row.provider = chosen
    if chosen == PROVIDER_OPENAI:
        row.base_url = OPENAI_BASE_URL
    else:
        row.base_url = (base_url or "").strip() or default_url
    row.model = (model or "").strip() or default_model
    row.timeout_seconds = timeout_seconds
    row.advice_style = normalize_advice_style(advice_style)
    if api_key is not None and api_key != "":
        row.api_key_encrypted = encrypt_secret(api_key)
    db.flush()
    return row
