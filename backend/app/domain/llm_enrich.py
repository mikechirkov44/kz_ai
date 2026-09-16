from __future__ import annotations

import json
import re
from typing import Any, Optional

from app.domain.ai_rules import PLAN_BEHIND_PERCENT
from app.domain.quarterly import matrix_row_dimensions

MAX_ENRICH_ITEMS = 30
TOP_CASES_LIMIT = 8
PLAYBOOK_LIMIT = 5
FOCUS_LIMIT = 5
WEAR_LIMIT = 5
DETAIL_KEYS = (
    "suggest_qty",
    "months_without_sales",
    "gap_percent",
    "plan_percent",
    "to_counterparty",
    "wear_type",
    "lts",
    "bundle",
    "strong_bundle",
    "client_avg_price",
    "shipment_avg_price",
    "sample_count",
)


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


def _as_float(raw: Any) -> Optional[float]:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.replace(" ", "").replace(",", "."))
        except ValueError:
            return None
    return None


def _details(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("details") or {}
    return raw if isinstance(raw, dict) else {}


def _client_name(item: dict[str, Any]) -> str:
    who = item.get("counterparty")
    return str(who) if who else "Без клиента"


def _item_score(item: dict[str, Any]) -> int:
    try:
        return int(item.get("score") or 0)
    except (TypeError, ValueError):
        return 0


def _is_exit_lts(details: dict[str, Any]) -> bool:
    return "вывод" in str(details.get("lts") or "").strip().lower()


def _compact_details(details: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in DETAIL_KEYS:
        val = details.get(key)
        if val is None or val == "" or val == "—":
            continue
        if key in ("suggest_qty", "gap_percent", "plan_percent", "client_avg_price", "shipment_avg_price"):
            num = _as_float(val)
            out[key] = round(num, 1) if num is not None else val
        elif key in ("months_without_sales", "sample_count"):
            num = _as_float(val)
            out[key] = int(num) if num is not None else val
        else:
            out[key] = val
    articles = _compact_articles(details.get("articles"))
    if articles:
        out["articles"] = articles
    return out


def _compact_articles(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        article = item.get("article")
        if not isinstance(article, str) or not article.strip():
            continue
        row: dict[str, Any] = {"article": article.strip()}
        gap = _as_float(item.get("gap_percent"))
        if gap is not None:
            row["gap_percent"] = round(gap, 1)
        client = _as_float(item.get("client_avg_price"))
        if client is not None:
            row["client_avg_price"] = round(client, 1)
        ship = _as_float(item.get("shipment_avg_price"))
        if ship is not None:
            row["shipment_avg_price"] = round(ship, 1)
        rows.append(row)
    return rows


def compact_recommendation_payload(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for i, item in enumerate(items):
        row: dict[str, Any] = {
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
        details = _compact_details(_details(item))
        if details:
            row["details"] = details
        rows.append(row)
    return rows


def _priority_key(item: dict[str, Any]) -> tuple[int, float, float]:
    details = _details(item)
    return (
        _item_score(item),
        _as_float(details.get("suggest_qty")) or 0.0,
        _as_float(details.get("gap_percent")) or 0.0,
    )


def _play_why(item: dict[str, Any]) -> str:
    details = _details(item)
    bits: list[str] = []
    plan = _as_float(details.get("plan_percent"))
    if plan is not None:
        bits.append(f"план {round(plan, 1)}%")
    months = _as_float(details.get("months_without_sales"))
    if months and months > 0:
        bits.append(f"{int(months)} мес. без продаж")
    gap = _as_float(details.get("gap_percent"))
    if gap is not None:
        bits.append(f"разрыв {round(gap, 1)}%")
    dest = details.get("to_counterparty")
    if isinstance(dest, str) and dest.strip():
        bits.append(f"→ {dest.strip()}")
    if item.get("type") == "mix":
        bits.append("перекос ассортимента")
    if _is_exit_lts(details):
        bits.append("ЖЦТ Вывод")
    return " · ".join(bits)


def _client_plan(rows: list[dict[str, Any]]) -> Optional[float]:
    shown: Optional[float] = None
    behind: Optional[float] = None
    threshold = float(PLAN_BEHIND_PERCENT)
    for item in rows:
        pct = _as_float(_details(item).get("plan_percent"))
        if pct is None:
            continue
        if shown is None:
            shown = pct
        if pct < threshold and (behind is None or pct < behind):
            behind = pct
    return behind if behind is not None else shown


def _build_playbook(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    steps: list[dict[str, Any]] = []
    for item in sorted(items, key=_priority_key, reverse=True):
        action = item.get("action")
        if action not in {"return", "restock", "transfer", "reprice"}:
            continue
        key = f"{_client_name(item)}:{action}"
        if key in seen:
            continue
        seen.add(key)
        steps.append(
            {
                "action": action,
                "counterparty": _client_name(item),
                "title": item.get("title") or item.get("message") or "",
                "why": _play_why(item),
            }
        )
        if len(steps) >= PLAYBOOK_LIMIT:
            break
    return steps


def _build_focus(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(_client_name(item), []).append(item)
    threshold = float(PLAN_BEHIND_PERCENT)
    rows: list[dict[str, Any]] = []
    for name, group in groups.items():
        top = max(group, key=_priority_key)
        plan = _client_plan(group)
        actions = []
        for item in group:
            action = item.get("action")
            if action and action not in actions:
                actions.append(str(action))
        rows.append(
            {
                "counterparty": name,
                "signals": len(group),
                "actions": actions,
                "title": top.get("title") or top.get("message") or "",
                "plan_percent": round(plan, 1) if plan is not None else None,
                "behind": plan is not None and plan < threshold,
                "score": _item_score(top),
            }
        )
    rows.sort(
        key=lambda row: (
            not row["behind"],
            row["plan_percent"] if row["behind"] and row["plan_percent"] is not None else 100.0,
            -int(row["score"] or 0),
            -int(row["signals"] or 0),
        )
    )
    return rows[:FOCUS_LIMIT]


def _build_wear(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        wear = _details(item).get("wear_type")
        if not isinstance(wear, str) or not wear.strip() or wear.strip() == "—":
            continue
        key = wear.strip()
        counts[key] = counts.get(key, 0) + 1
    return [
        {"wear": wear, "signals": count}
        for wear, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:WEAR_LIMIT]
    ]


def _top_cases(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(enumerate(items), key=lambda pair: _priority_key(pair[1]), reverse=True)
    cases = []
    for index, item in ranked[:TOP_CASES_LIMIT]:
        row: dict[str, Any] = {
            "index": index,
            "type": item.get("type"),
            "action": item.get("action"),
            "counterparty": _client_name(item),
            "title": item.get("title") or item.get("message") or "",
            "score": _item_score(item),
            "why": _play_why(item),
        }
        details = _compact_details(_details(item))
        if details:
            row["details"] = details
        cases.append(row)
    return cases


def build_llm_digest(items: list[dict[str, Any]]) -> dict[str, Any]:
    actions = {"return": 0, "restock": 0, "transfer": 0, "reprice": 0}
    severity = {"high": 0, "medium": 0, "info": 0}
    clients: set[str] = set()
    gaps: list[float] = []
    return_qty = 0.0
    restock_qty = 0.0
    transfer_qty = 0.0
    mix_count = 0
    exit_lts = 0
    plan_by_client: dict[str, float] = {}
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
        details = _details(item)
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
        if item.get("type") == "mix":
            mix_count += 1
        if _is_exit_lts(details):
            exit_lts += 1
        plan = _as_float(details.get("plan_percent"))
        if who and plan is not None:
            name = str(who)
            prev = plan_by_client.get(name)
            if prev is None or plan < prev:
                plan_by_client[name] = plan
    threshold = float(PLAN_BEHIND_PERCENT)
    behind = sum(1 for pct in plan_by_client.values() if pct < threshold)
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
        "mix_count": mix_count,
        "exit_lts": exit_lts,
        "behind_plan": behind,
        "plan_known": len(plan_by_client),
        "wear": _build_wear(items),
        "playbook": _build_playbook(items),
        "focus": _build_focus(items),
        "top_cases": _top_cases(items),
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
        for key in ("return", "restock", "transfer", "reprice", "focus", "playbook", "avoid")
    }
    return {
        "headline": _note(data.get("headline")),
        "situation": _note(data.get("situation") or data.get("summary")),
        "notes": {key: value for key, value in notes.items() if value},
    }


def build_enrich_messages(items: list[dict[str, Any]], digest: Optional[dict[str, Any]] = None) -> list[dict[str, str]]:
    resolved = digest or build_llm_digest(items)
    payload = {
        "digest": resolved,
        "items": compact_recommendation_payload(items),
    }
    system = (
        "Ты аналитик ювелирного опта. Пиши по-русски для руководителя. "
        "Не выдумывай цифры и не округляй по-своему: истина — digest "
        "(playbook, focus, top_cases, wear, behind_plan). items — только для comments. "
        "headline — одна фраза, что сделать на этой неделе. "
        "situation — 2–3 предложения: обстановка и кому звонить первым по digest.playbook. "
        "notes.playbook — 2–4 шага строго по digest.playbook, без новых цифр. "
        "notes.avoid — что не делать (не возить ЖЦТ «Вывод», не раздувать мелкие перекладки, "
        "если возврат и отставание от плана важнее). "
        "notes.return / restock / transfer / reprice / focus — по 1–2 предложения; "
        "если в digest действие = 0, так и скажи. "
        "По каждой item — совет менеджеру 1–2 предложения. "
        "Верни только JSON: "
        '{"headline":"...","situation":"...","summary":"...","notes":{"playbook":"...","avoid":"...","return":"...","restock":"...","transfer":"...","reprice":"...","focus":"..."},'
        '"comments":[{"index":0,"comment":"..."}]} '
        "summary можешь повторить situation. Число comments и index как у items."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def slice_for_enrichment(items: list[dict[str, Any]], limit: int = MAX_ENRICH_ITEMS) -> list[dict[str, Any]]:
    return items[: max(limit, 0)]


MAX_MATRIX_CELLS = 40


def parse_llm_cell_texts(content: str, expected_len: int) -> list[Optional[str]]:
    texts: list[Optional[str]] = [None] * max(expected_len, 0)
    if expected_len <= 0:
        return texts
    try:
        data = extract_json_value(content)
    except (json.JSONDecodeError, TypeError, ValueError):
        return texts
    rows: Any = None
    if isinstance(data, dict):
        rows = data.get("cells") or data.get("comments") or data.get("items")
    elif isinstance(data, list):
        rows = data
    if not isinstance(rows, list):
        return texts
    for i, row in enumerate(rows):
        if isinstance(row, str):
            if i < expected_len and row.strip():
                texts[i] = row.strip()
            continue
        if not isinstance(row, dict):
            continue
        idx_raw = row.get("index", i)
        try:
            idx = int(idx_raw)
        except (TypeError, ValueError):
            idx = i
        text = row.get("text") or row.get("comment") or row.get("message")
        if isinstance(text, str) and text.strip() and 0 <= idx < expected_len:
            texts[idx] = text.strip()
    return texts


def apply_llm_cell_texts(
    rows: list[dict[str, Any]],
    texts: list[Optional[str]],
    cells: list[dict[str, Any]] | None = None,
) -> None:
    for i, (row, text) in enumerate(zip(rows, texts)):
        if not text:
            continue
        payload = cells[i] if cells and i < len(cells) else None
        rules = payload.get("rules") if isinstance(payload, dict) else None
        if isinstance(rules, list) and cell_rules_have_facts(rules) and not re.search(r"\d", text):
            continue
        row["recommendations_llm"] = text
        row["recommendations_text"] = text


def cell_rules_have_facts(rules: list[Any]) -> bool:
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        details = rule.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        for key in ("gap_percent", "suggest_qty", "plan_percent", "client_avg_price", "months_without_sales"):
            if _as_float(details.get(key)) is not None:
                return True
        if details.get("articles") or rule.get("article"):
            return True
        if re.search(r"\d", str(rule.get("title") or "") + str(rule.get("message") or "")):
            return True
    return False


def refresh_client_recommendation_texts(clients: list[dict[str, Any]]) -> None:
    for client in clients:
        if not any(row.get("recommendations_llm") for row in (client.get("matrix") or []) if isinstance(row, dict)):
            continue
        parts: list[str] = []
        for row in client.get("matrix") or []:
            if not isinstance(row, dict):
                continue
            text = str(row.get("recommendations_text") or "").strip()
            if text and text not in parts:
                parts.append(text)
        if parts:
            client["recommendations_text"] = " · ".join(parts)


def collect_matrix_cell_payload(
    clients: list[dict[str, Any]],
    limit: int = MAX_MATRIX_CELLS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    found: list[tuple[int, dict[str, Any], list[dict[str, Any]], str]] = []
    for client in clients:
        name = str(client.get("counterparty") or "")
        for row in client.get("matrix") or []:
            if not isinstance(row, dict):
                continue
            recs = [item for item in (row.get("recommendations") or []) if isinstance(item, dict)]
            if not recs:
                continue
            score = max((_item_score(item) for item in recs), default=0)
            found.append((score, row, recs, name))
    found.sort(key=lambda item: -item[0])
    payload: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    for i, (_, row, recs, name) in enumerate(found[: max(limit, 0)]):
        payload.append(
            {
                "index": i,
                "counterparty": name,
                "is_total": bool(row.get("is_total")),
                "dimensions": sorted(matrix_row_dimensions(row)),
                "rules": compact_recommendation_payload(recs),
            }
        )
        refs.append(row)
    return payload, refs


def build_cell_enrich_messages(cells: list[dict[str, Any]]) -> list[dict[str, str]]:
    system = (
        "Ты аналитик ювелирного опта. Пиши по-русски для менеджера в ячейку таблицы. "
        "По каждой cell — одна фраза (до 180 знаков). "
        "Цифры из rules обязательны: gap_percent, suggest_qty, article, client_avg_price, months_without_sales. "
        "Не пересказывай title без цифр и не выдумывай цифры. "
        "Пример: «Браслет −21%: ART-1 (−24%), ART-2; следующие отгрузки не выше 45 000 ₸». "
        "Не переноси совет на другую строку и не пиши про категории, которых нет в dimensions. "
        "is_total true — строка «Итого»: только то, что не привязалось к категории (план, перекладка без измерения). "
        "Верни только JSON: "
        '{"cells":[{"index":0,"text":"..."}]} '
        "Число cells и index как у входа."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps({"cells": cells}, ensure_ascii=False)},
    ]
