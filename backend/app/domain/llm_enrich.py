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
            "action": item.get("action"),
            "title": item.get("title"),
            "score": item.get("score"),
            "counterparty": item.get("counterparty"),
            "article": item.get("article"),
            "message": item.get("message"),
        }
        for i, item in enumerate(items)
    ]


def _as_float(raw: Any) -> Optional[float]:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.replace(" ", "").replace(",", "."))
        except ValueError:
            return None
    return None


def build_llm_digest(items: list[dict[str, Any]]) -> dict[str, Any]:
    actions = {"return": 0, "restock": 0, "transfer": 0, "reprice": 0}
    severity = {"high": 0, "medium": 0, "info": 0}
    clients: set[str] = set()
    gaps: list[float] = []
    return_qty = 0.0
    restock_qty = 0.0
    transfer_qty = 0.0
    for item in items:
        action = item.get("action")
        if action in actions:
            actions[action] += 1
        sev = item.get("severity")
        if sev == "high":
            severity["high"] += 1
        elif sev == "medium":
            severity["medium"] += 1
        else:
            severity["info"] += 1
        who = item.get("counterparty")
        if who:
            clients.add(str(who))
        details = item.get("details") or {}
        qty = _as_float(details.get("suggest_qty")) or 0.0
        if action == "return":
            return_qty += qty
        elif action == "restock":
            restock_qty += qty
        elif action == "transfer":
            transfer_qty += qty
        gap = _as_float(details.get("gap_percent"))
        if gap is not None:
            gaps.append(gap)
    return {
        "total": len(items),
        "clients": len(clients),
        "actions": actions,
        "severity": severity,
        "return_qty": round(return_qty, 1),
        "restock_qty": round(restock_qty, 1),
        "transfer_qty": round(transfer_qty, 1),
        "avg_price_gap": round(sum(gaps) / len(gaps), 1) if gaps else None,
        "max_price_gap": round(max(gaps), 1) if gaps else None,
    }


def parse_llm_summary(content: str) -> Optional[str]:
    try:
        data = extract_json_value(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    summary = data.get("summary") or data.get("headline")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return None


def _note(raw: Any) -> str:
    return raw.strip() if isinstance(raw, str) and raw.strip() else ""


def parse_llm_report(content: str) -> dict[str, Any]:
    empty = {"headline": "", "situation": "", "notes": {}}
    try:
        data = extract_json_value(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return empty
    if not isinstance(data, dict):
        return empty
    notes_raw = data.get("notes") if isinstance(data.get("notes"), dict) else {}
    notes = {
        key: _note(notes_raw.get(key) or data.get(key))
        for key in ("return", "restock", "transfer", "reprice", "focus")
    }
    return {
        "headline": _note(data.get("headline")),
        "situation": _note(data.get("situation") or data.get("summary")),
        "notes": {key: value for key, value in notes.items() if value},
    }


def build_enrich_messages(items: list[dict[str, Any]], digest: Optional[dict[str, Any]] = None) -> list[dict[str, str]]:
    payload = {
        "digest": digest or build_llm_digest(items),
        "items": compact_recommendation_payload(items),
    }
    system = (
        "Ты аналитик ювелирного опта. Пиши по-русски для руководителя. "
        "Не выдумывай цифры: используй только digest и items. "
        "По каждой рекомендации — совет менеджеру 1–2 предложения. "
        "Для отчёта заполни headline (одна фраза), situation (2–3 предложения), "
        "notes.return / notes.restock / notes.transfer / notes.reprice / notes.focus "
        "(по 1–2 предложения; если в digest действие = 0, так и скажи). "
        "Верни только JSON: "
        '{"headline":"...","situation":"...","summary":"...","notes":{"return":"...","restock":"...","transfer":"...","reprice":"...","focus":"..."},'
        '"comments":[{"index":0,"comment":"..."}]} '
        "summary можешь повторить situation. Число comments и index как у items."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def slice_for_enrichment(items: list[dict[str, Any]], limit: int = MAX_ENRICH_ITEMS) -> list[dict[str, Any]]:
    return items[: max(limit, 0)]
