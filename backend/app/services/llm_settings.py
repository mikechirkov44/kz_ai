"""Admin LLM settings: encrypted API key, OpenAI-compatible endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LlmSettings
from app.security import decrypt_secret, encrypt_secret

DEFAULT_SLUG = "default"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
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
    return {
        "enabled": bool(row.enabled),
        "provider": row.provider or "openai_compatible",
        "base_url": row.base_url or "",
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
) -> LlmSettings:
    row = get_llm_row(db)
    row.enabled = enabled
    row.provider = "openai_compatible"
    row.base_url = (base_url or "").strip()
    row.model = (model or "").strip() or DEFAULT_MODEL
    row.timeout_seconds = timeout_seconds
    row.advice_style = normalize_advice_style(advice_style)
    if api_key is not None and api_key != "":
        row.api_key_encrypted = encrypt_secret(api_key)
    db.flush()
    return row
