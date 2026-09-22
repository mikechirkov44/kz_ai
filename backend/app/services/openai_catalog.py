"""Official OpenAI model catalog for the admin LLM picker."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.domain.llm_enrich import normalize_openai_base_url

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODELS_URL = f"{OPENAI_BASE_URL}/models"
OPENAI_DEFAULT_MODEL = "gpt-6-astra"
SKIP_MARKERS = (
    "embedding",
    "whisper",
    "tts",
    "dall-e",
    "davinci",
    "babbage",
    "moderation",
    "sora",
    "transcribe",
    "realtime",
)
PRESET_MODELS = (
    {"id": "gpt-6-astra", "name": "GPT-6 Astra"},
    {"id": "gpt-5.6", "name": "GPT-5.6"},
    {"id": "gpt-5.4", "name": "GPT-5.4"},
    {"id": "gpt-5", "name": "GPT-5"},
    {"id": "gpt-4o", "name": "GPT-4o"},
    {"id": "gpt-4o-mini", "name": "GPT-4o mini"},
    {"id": "o4-mini", "name": "o4-mini"},
    {"id": "o3", "name": "o3"},
)


def looks_like_openai(base_url: str) -> bool:
    host = urlparse(normalize_openai_base_url(base_url)).hostname or ""
    return host.endswith("openai.com") and "openrouter" not in host


def is_chat_model(model_id: str) -> bool:
    ident = (model_id or "").strip().lower()
    if not ident or any(marker in ident for marker in SKIP_MARKERS):
        return False
    return ident.startswith(("gpt-", "o1", "o3", "o4", "chatgpt")) or "astra" in ident


def _entry(model_id: str, name: str = "") -> dict[str, str]:
    label = (name or model_id).strip() or model_id
    return {"id": model_id, "name": label, "price_label": "по тарифу OpenAI"}


def group_openai_models(rows: list[Any]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("id") or "").strip()
        if not is_chat_model(model_id) or model_id in by_id:
            continue
        by_id[model_id] = _entry(model_id, str(row.get("name") or ""))
    for preset in PRESET_MODELS:
        by_id.setdefault(preset["id"], _entry(preset["id"], preset["name"]))
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    for preset in PRESET_MODELS:
        entry = by_id.get(preset["id"])
        if entry:
            ordered.append(entry)
            seen.add(preset["id"])
    rest = sorted((item for key, item in by_id.items() if key not in seen), key=lambda item: item["id"])
    return [{"id": "openai", "label": "OpenAI", "models": ordered + rest}]


def fetch_openai_models(
    api_key: str,
    *,
    client: Optional[httpx.Client] = None,
    timeout: float = 8.0,
) -> list[dict[str, Any]]:
    if not (api_key or "").strip():
        return []
    own = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        response = http.get(
            OPENAI_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key.strip()}"},
        )
        if response.status_code >= 400:
            return []
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []
    finally:
        if own:
            http.close()
    rows = payload.get("data") if isinstance(payload, dict) else payload
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def openai_model_groups(
    api_key: str = "",
    *,
    client: Optional[httpx.Client] = None,
    timeout: float = 8.0,
) -> list[dict[str, Any]]:
    return group_openai_models(fetch_openai_models(api_key, client=client, timeout=timeout))
