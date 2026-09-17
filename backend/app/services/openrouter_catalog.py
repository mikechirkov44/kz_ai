"""OpenRouter model catalog grouped from free to premium."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.domain.llm_enrich import normalize_openai_base_url

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
GROUP_LIMIT = 40
SKIP_SUFFIXES = {"nitro", "floor", "extended", "thinking", "online"}
TIER_ORDER = ("free", "cheap", "premium")
TIER_LABELS = {
    "free": "Free",
    "cheap": "Недорого",
    "premium": "Премиум",
}


def _as_float(raw: Any) -> Optional[float]:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def price_per_million(raw: Any) -> float:
    per_token = _as_float(raw)
    if per_token is None:
        return 0.0
    return per_token * 1_000_000


def format_price_label(prompt_m: float, completion_m: float, *, free: bool) -> str:
    if free:
        return "бесплатно"
    if prompt_m <= 0 and completion_m <= 0:
        return "бесплатно"
    return f"${prompt_m:.2f} / ${completion_m:.2f} за 1M"


def classify_tier(model_id: str, prompt_m: float, completion_m: float) -> str:
    ident = (model_id or "").strip().lower()
    if ident.endswith(":free") or ident == "openrouter/free" or (prompt_m <= 0 and completion_m <= 0):
        return "free"
    cost = max(prompt_m, completion_m)
    if cost < 1.0:
        return "cheap"
    return "premium"


def _skip_variant(model_id: str) -> bool:
    ident = (model_id or "").strip()
    if ":" not in ident:
        return False
    suffix = ident.rsplit(":", 1)[-1].lower()
    return suffix in SKIP_SUFFIXES


def _is_text_output(row: dict[str, Any]) -> bool:
    arch = row.get("architecture") if isinstance(row.get("architecture"), dict) else {}
    outputs = arch.get("output_modalities") or arch.get("modality") or []
    if isinstance(outputs, str):
        return "text" in outputs.lower()
    if isinstance(outputs, list):
        if not outputs:
            return True
        return any("text" in str(item).lower() for item in outputs)
    return True


def catalog_entry(row: dict[str, Any]) -> Optional[dict[str, str]]:
    if not isinstance(row, dict):
        return None
    model_id = str(row.get("id") or "").strip()
    if not model_id or _skip_variant(model_id) or not _is_text_output(row):
        return None
    pricing = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
    prompt_m = price_per_million(pricing.get("prompt"))
    completion_m = price_per_million(pricing.get("completion"))
    tier = classify_tier(model_id, prompt_m, completion_m)
    name = str(row.get("name") or model_id).strip() or model_id
    return {
        "id": model_id,
        "name": name,
        "tier": tier,
        "price_label": format_price_label(prompt_m, completion_m, free=tier == "free"),
    }


def group_openrouter_models(rows: list[Any], *, limit: int = GROUP_LIMIT) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, str]]] = {key: [] for key in TIER_ORDER}
    seen: set[str] = set()
    for row in rows:
        entry = catalog_entry(row if isinstance(row, dict) else {})
        if not entry or entry["id"] in seen:
            continue
        seen.add(entry["id"])
        buckets[entry["tier"]].append(entry)
    groups = []
    cap = max(limit, 1)
    for tier in TIER_ORDER:
        models = buckets[tier][:cap]
        if not models:
            continue
        groups.append({"id": tier, "label": TIER_LABELS[tier], "models": models})
    return groups


def fetch_openrouter_models(*, client: Optional[httpx.Client] = None, timeout: float = 8.0) -> list[dict[str, Any]]:
    own = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        response = http.get(OPENROUTER_MODELS_URL)
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


def openrouter_model_groups(*, client: Optional[httpx.Client] = None, timeout: float = 8.0) -> list[dict[str, Any]]:
    return group_openrouter_models(fetch_openrouter_models(client=client, timeout=timeout))


def looks_like_openrouter(base_url: str) -> bool:
    host = normalize_openai_base_url(base_url).lower()
    return "openrouter.ai" in host
