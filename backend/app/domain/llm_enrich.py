from __future__ import annotations

import json
import re
from typing import Any, Optional

MAX_ENRICH_ITEMS = 30


def normalize_openai_base_url(base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")].rstrip("/")
    return url


def chat_completions_url(base_url: str) -> str:
    base = normalize_openai_base_url(base_url)
    if not base:
        return ""
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def extract_json_value(text: str) -> Any:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for open_ch, close_ch in (("{", "}"), ("[", "]")):
            start = raw.find(open_ch)
            end = raw.rfind(close_ch)
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise


def parse_llm_comments(content: str, expected_len: int) -> list[Optional[str]]:
    comments: list[Optional[str]] = [None] * max(expected_len, 0)
    if expected_len <= 0:
        return comments
    try:
        data = extract_json_value(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return comments

    rows: Any = None
    if isinstance(data, dict):
        rows = data.get("comments") or data.get("items")
    elif isinstance(data, list):
        rows = data
    if not isinstance(rows, list):
        return comments

    for i, row in enumerate(rows):
        if isinstance(row, str):
            if i < expected_len and row.strip():
                comments[i] = row.strip()
            continue
        if not isinstance(row, dict):
            continue
        idx_raw = row.get("index", i)
        try:
            idx = int(idx_raw)
        except (TypeError, ValueError):
            idx = i
        comment = row.get("comment") or row.get("text") or row.get("message")
        if isinstance(comment, str) and comment.strip() and 0 <= idx < expected_len:
            comments[idx] = comment.strip()
    return comments


def apply_llm_comments(items: list[dict[str, Any]], comments: list[Optional[str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        copy = dict(item)
        if i < len(comments) and comments[i]:
            copy["llm_comment"] = comments[i]
        out.append(copy)
    return out


def compact_recommendation_payload(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": i,
            "type": item.get("type"),
            "severity": item.get("severity"),
            "counterparty": item.get("counterparty"),
            "article": item.get("article"),
            "message": item.get("message"),
        }
        for i, item in enumerate(items)
    ]


def build_enrich_messages(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    payload = compact_recommendation_payload(items)
    system = (
        "Ты аналитик ювелирного опта. По каждой рекомендации дай короткий совет менеджеру на русском "
        "(1–2 предложения): что сделать и зачем. Не выдумывай цифры и факты, которых нет во входе. "
        'Верни только JSON вида {"comments":[{"index":0,"comment":"..."}]} '
        "с тем же числом элементов и теми же index."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def slice_for_enrichment(items: list[dict[str, Any]], limit: int = MAX_ENRICH_ITEMS) -> list[dict[str, Any]]:
    return items[: max(limit, 0)]
