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
    "avg_turnover",
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


_CELL_TEXT_KEYS = ("text", "comment", "message", "advice", "tip", "совет", "рекомендация")


def _cell_row_text(row: dict[str, Any]) -> Optional[str]:
    for key in _CELL_TEXT_KEYS:
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _iter_json_values(raw: str):
    decoder = json.JSONDecoder()
    text = raw or ""
    idx = 0
    while idx < len(text):
        start = None
        for pos in range(idx, len(text)):
            if text[pos] in "{[":
                start = pos
                break
        if start is None:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            idx = start + 1
            continue
        yield obj
        idx = max(end, start + 1)


def _rows_from_payload(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    rows = (
        data.get("cells")
        or data.get("comments")
        or data.get("items")
        or data.get("advice")
        or data.get("tips")
    )
    if isinstance(rows, list):
        return rows
    if _cell_row_text(data):
        return [data]
    return []


def _fill_indexed_texts(slots: list[Optional[str]], data: Any) -> None:
    expected = len(slots)
    if isinstance(data, dict):
        for key, val in data.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            text = None
            if isinstance(val, str):
                text = val.strip()
            elif isinstance(val, dict):
                text = _cell_row_text(val)
            if text and 0 <= idx < expected and slots[idx] is None:
                slots[idx] = text
    for i, row in enumerate(_rows_from_payload(data)):
        if isinstance(row, str):
            if i < expected and row.strip() and slots[i] is None:
                slots[i] = row.strip()
            continue
        if not isinstance(row, dict):
            continue
        idx_raw = row.get("index", i)
        try:
            idx = int(idx_raw)
        except (TypeError, ValueError):
            idx = i
        text = _cell_row_text(row)
        if text and 0 <= idx < expected and slots[idx] is None:
            slots[idx] = text


def _salvage_plain_texts(content: str, expected_len: int) -> list[Optional[str]]:
    slots: list[Optional[str]] = [None] * max(expected_len, 0)
    raw = (content or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json|text)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    if not raw or expected_len <= 0:
        return slots
    from_fields = _salvage_json_field_texts(raw, expected_len)
    if any(from_fields):
        return from_fields
    if raw.lstrip()[:1] in "{[":
        return slots
    numbered = [
        part.strip(" \t-•")
        for part in re.split(r"(?:^|\n)\s*(?:\d+[.)]|(?:cell|ячейка)\s*\d+)\s*", raw, flags=re.I)
        if part.strip()
    ]
    if len(numbered) >= expected_len and (expected_len > 1 or raw[:2].strip()[:1].isdigit()):
        for i in range(expected_len):
            slots[i] = numbered[i][:500]
        return slots
    if expected_len > 1:
        blocks = [part.strip() for part in re.split(r"\n\s*\n", raw) if part.strip()]
        if len(blocks) >= expected_len:
            for i in range(expected_len):
                slots[i] = blocks[i][:500]
            return slots
    if expected_len == 1:
        text = re.sub(r"^(?:ответ|совет|рекомендация)\s*[:—-]\s*", "", raw, flags=re.I).strip()
        if len(text) >= _PLAIN_ADVICE_MIN:
            slots[0] = text[:500]
    return slots


_JSON_TEXT_FIELD = re.compile(
    r'"(?:comment|text|message|advice|tip|совет|рекомендация)"\s*:\s*"((?:\\.|[^"\\])*)(?:"|$)',
    re.I,
)
_PLAIN_ADVICE_MIN = 24


def _unescape_json_fragment(raw: str) -> str:
    try:
        return str(json.loads(f'"{raw}"'))
    except json.JSONDecodeError:
        return raw.replace(r"\"", '"').replace(r"\n", "\n")


def _salvage_json_field_texts(raw: str, expected_len: int) -> list[Optional[str]]:
    slots: list[Optional[str]] = [None] * max(expected_len, 0)
    found = [
        _unescape_json_fragment(match.group(1)).strip()[:500]
        for match in _JSON_TEXT_FIELD.finditer(raw or "")
        if match.group(1).strip()
    ]
    for i, text in enumerate(found[: len(slots)]):
        slots[i] = text
    return slots


def parse_indexed_llm_texts(content: str, expected_len: int) -> list[Optional[str]]:
    slots: list[Optional[str]] = [None] * max(expected_len, 0)
    if expected_len <= 0:
        return slots
    complete: Any = None
    try:
        complete = extract_json_value(content)
        _fill_indexed_texts(slots, complete)
    except (json.JSONDecodeError, TypeError, ValueError):
        complete = None
    if not any(slots):
        for obj in _iter_json_values(content):
            _fill_indexed_texts(slots, obj)
    if any(slots):
        return slots
    if complete is not None:
        return slots
    return _salvage_plain_texts(content, expected_len)


def parse_llm_comments(content: str, expected_len: int) -> list[Optional[str]]:
    return parse_indexed_llm_texts(content, expected_len)


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
        if key in ("suggest_qty", "gap_percent", "plan_percent", "client_avg_price", "shipment_avg_price", "avg_turnover"):
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


def _normalize_advice_style(style: Optional[str]) -> str:
    value = (style or "").strip().lower()
    if value in ("economy", "standard", "detailed"):
        return value
    return "standard"


def build_report_enrich_messages(
    digest: dict[str, Any],
    *,
    style: Optional[str] = None,
) -> list[dict[str, str]]:
    mode = _normalize_advice_style(style)
    if mode == "economy":
        length = (
            "headline — одна короткая фраза. situation — 1 предложение. "
            "notes — по одной короткой фразе, пустые можно опустить. "
        )
    elif mode == "detailed":
        length = (
            "headline — одна фраза. situation — 3–4 предложения: обстановка и кому звонить первым по digest.playbook. "
            "notes.playbook — 3–5 шагов. Остальные notes — по 2 предложения. "
        )
    else:
        length = (
            "headline — одна фраза, что сделать на этой неделе. "
            "situation — 2–3 предложения: обстановка и кому звонить первым по digest.playbook. "
            "notes.playbook — 2–4 шага строго по digest.playbook, без новых цифр. "
        )
    system = (
        "Ты аналитик ювелирного опта. Пиши по-русски для руководителя. "
        "Не выдумывай цифры и не округляй по-своему: истина — digest "
        "(playbook, focus, top_cases, wear, behind_plan). "
        + length
        + "notes.avoid — что не делать (не возить ЖЦТ «Вывод», не раздувать мелкие перекладки, "
        "если возврат и отставание от плана важнее). "
        "notes.return / restock / transfer / reprice / focus — по смыслу; "
        "если в digest действие = 0, так и скажи. "
        "Верни только JSON, без comments: "
        '{"headline":"...","situation":"...","summary":"...","notes":{"playbook":"...","avoid":"...","return":"...","restock":"...","transfer":"...","reprice":"...","focus":"..."}} '
        "summary можешь повторить situation."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _json_dumps({"digest": digest})},
    ]


def build_comment_enrich_messages(
    items: list[dict[str, Any]],
    *,
    style: Optional[str] = None,
) -> list[dict[str, str]]:
    numbered = compact_recommendation_payload(items)
    mode = _normalize_advice_style(style)
    if mode == "economy":
        how = "1 короткая фраза (до 120 знаков): что сделать первым."
    elif mode == "detailed":
        how = (
            "2–3 живые фразы (до 320 знаков): зачем сейчас, первый ход, что сказать на звонке. "
            "Цифра и артикул только из item."
        )
    else:
        how = "1–2 живые фразы (до 180 знаков): что сделать первым и что сказать на звонке."
    system = (
        "Ты аналитик ювелирного опта. Пиши по-русски совет менеджеру по каждой item. "
        f"{how} "
        "Цифры и артикулы только из item. Не выдумывай. "
        "Верни только JSON: "
        '{"comments":[{"index":0,"comment":"..."}]} '
        "Число comments и index как у items. Не используй markdown."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _json_dumps({"items": numbered})},
    ]


def build_enrich_messages(items: list[dict[str, Any]], digest: Optional[dict[str, Any]] = None) -> list[dict[str, str]]:
    resolved = digest or build_llm_digest(items)
    return build_report_enrich_messages(resolved)


def llm_report_is_useful(report: Optional[dict[str, Any]]) -> bool:
    if not isinstance(report, dict):
        return False
    if str(report.get("headline") or "").strip() or str(report.get("situation") or "").strip():
        return True
    notes = report.get("notes")
    return bool(isinstance(notes, dict) and any(notes.values()))


def slice_for_enrichment(items: list[dict[str, Any]], limit: int = MAX_ENRICH_ITEMS) -> list[dict[str, Any]]:
    return items[: max(limit, 0)]


MAX_MATRIX_CELLS = 40
COMMENT_BATCH_SIZE = 4
MATRIX_BATCH_SIZE = 1


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def parse_llm_cell_texts(content: str, expected_len: int) -> list[Optional[str]]:
    return parse_indexed_llm_texts(content, expected_len)


def apply_llm_cell_texts(
    rows: list[dict[str, Any]],
    texts: list[Optional[str]],
    cells: list[dict[str, Any]] | None = None,
) -> None:
    for i, (row, text) in enumerate(zip(rows, texts)):
        if not text:
            continue
        facts = str(row.get("recommendations_text") or "")
        if cells and i < len(cells) and isinstance(cells[i], dict):
            facts = str(cells[i].get("facts") or facts)
        if not advice_is_useful(text, facts):
            continue
        row["recommendations_llm"] = text.strip()


_ADVICE_CUES = (
    "сначала",
    "звон",
    "не вези",
    "не воз",
    "не довози",
    "не отгруж",
    "назовите",
    "начн",
    "забер",
    "на этой неделе",
    "сегодня",
    "потом ",
    "не клад",
    "не возите",
    "на звонке",
    "если клиент",
    "скажите",
    "не обеща",
    "просит",
)
_ADVICE_MIN_LEN = 40
_ADVICE_MIN_UNIQUE = 4
_ADVICE_MAX_OVERLAP = 0.55


def _norm_advice(text: str) -> str:
    cleaned = re.sub(r"[«»\"']", "", text or "")
    return re.sub(r"\s+", " ", cleaned.lower()).strip()


def _advice_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[а-яёa-z0-9\-]+", text) if len(w) > 3}


def advice_is_useful(advice: str, facts: str) -> bool:
    text = (advice or "").strip()
    if len(text) < _ADVICE_MIN_LEN:
        return False
    a = _norm_advice(text)
    f = _norm_advice(facts)
    if f and (a == f or a in f):
        return False
    if not any(cue in a for cue in _ADVICE_CUES):
        return False
    words_a = _advice_words(a)
    if not words_a:
        return False
    words_f = _advice_words(f)
    unique = words_a - words_f
    if len(unique) < _ADVICE_MIN_UNIQUE:
        return False
    overlap = len(words_a & words_f) / len(words_a)
    return overlap < _ADVICE_MAX_OVERLAP


def refresh_client_recommendation_texts(clients: list[dict[str, Any]]) -> None:
    for client in clients:
        tips: list[str] = []
        for row in client.get("matrix") or []:
            if not isinstance(row, dict):
                continue
            tip = str(row.get("recommendations_llm") or "").strip()
            if tip and tip not in tips:
                tips.append(tip)
        if tips:
            client["recommendations_llm"] = " ".join(tips)


def collect_matrix_cell_payload(
    clients: list[dict[str, Any]],
    limit: int = MAX_MATRIX_CELLS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    found: list[tuple[int, dict[str, Any], dict[str, Any], list[dict[str, Any]]]] = []
    for client in clients:
        for row in client.get("matrix") or []:
            if not isinstance(row, dict):
                continue
            recs = [item for item in (row.get("recommendations") or []) if isinstance(item, dict)]
            if not recs:
                continue
            score = max((_item_score(item) for item in recs), default=0)
            found.append((score, client, row, recs))
    found.sort(key=lambda item: -item[0])
    payload: list[dict[str, Any]] = []
    refs: list[dict[str, Any]] = []
    for i, (_, client, row, recs) in enumerate(found[: max(limit, 0)]):
        rules = _cell_rules_brief(recs)
        payload.append(
            {
                "index": i,
                "counterparty": str(client.get("counterparty") or ""),
                "is_total": bool(row.get("is_total")),
                "dimensions": sorted(matrix_row_dimensions(row)),
                "work_type": client.get("work_type_label") or client.get("work_type"),
                "plan_percent": client.get("shipment_percent"),
                "plan": client.get("plan"),
                "facts": row.get("recommendations_text") or "",
                "rules": rules,
            }
        )
        refs.append(row)
    return payload, refs


def _cell_rules_brief(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in recs[:4]:
        row: dict[str, Any] = {}
        for key in ("action", "title", "article"):
            val = item.get(key)
            if val not in (None, "", "—"):
                row[key] = val
        details = _compact_details(_details(item))
        brief: dict[str, Any] = {}
        for key in ("gap_percent", "suggest_qty", "plan_percent", "months_without_sales", "client_avg_price"):
            if key in details:
                brief[key] = details[key]
        articles = details.get("articles")
        if isinstance(articles, list) and articles:
            brief["articles"] = articles[:2]
        if brief:
            row["details"] = brief
        if row:
            out.append(row)
    return out


def reindex_matrix_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numbered: list[dict[str, Any]] = []
    for i, cell in enumerate(cells):
        row = dict(cell)
        row["index"] = i
        numbered.append(row)
    return numbered


def cells_to_comment_items(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for cell in reindex_matrix_cells(cells):
        rules = [rule for rule in (cell.get("rules") or []) if isinstance(rule, dict)]
        articles: list[dict[str, Any]] = []
        for rule in rules:
            article = rule.get("article")
            if isinstance(article, str) and article.strip():
                articles.append({"article": article.strip()})
            nested = (rule.get("details") or {}).get("articles") if isinstance(rule.get("details"), dict) else None
            if isinstance(nested, list):
                for row in nested[:2]:
                    if isinstance(row, dict) and row.get("article"):
                        articles.append({"article": str(row["article"])})
        details: dict[str, Any] = {}
        if cell.get("work_type"):
            details["work_type"] = cell.get("work_type")
        if cell.get("plan_percent") is not None:
            details["plan_percent"] = cell.get("plan_percent")
        if articles:
            details["articles"] = articles[:3]
        facts = str(cell.get("facts") or "")[:240]
        items.append(
            {
                "counterparty": cell.get("counterparty"),
                "action": rules[0].get("action") if rules else None,
                "title": facts,
                "message": facts,
                "article": articles[0]["article"] if articles else None,
                "details": details,
            }
        )
    return items


def build_cell_enrich_messages(
    cells: list[dict[str, Any]],
    *,
    style: Optional[str] = None,
) -> list[dict[str, str]]:
    mode = _normalize_advice_style(style)
    if mode == "economy":
        how = "1 короткая фраза (до 160 знаков): что сделать сейчас. "
    elif mode == "detailed":
        how = (
            "3 пункта через « · » (до 480 знаков): зачем сейчас; первый ход; что сказать и не обещать. "
            "Можно назвать артикул и цифру из item. "
        )
    else:
        how = "3 пункта через « · » (до 320 знаков): зачем сейчас; первый ход; что сказать и не обещать. "
    system = (
        "Ты аналитик ювелирного опта. По каждой item напиши совет менеджеру по-русски. "
        + how
        + "Цифры и артикулы только из item. Не копируй title целиком. "
        "Если item одна — верни только текст совета, без JSON и без нумерации. "
        "Если item несколько — нумерованный список 1. 2. 3. или JSON "
        '{"comments":[{"index":0,"comment":"..."}]} '
        "Не используй markdown."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": _json_dumps({"items": compact_recommendation_payload(cells_to_comment_items(cells))})},
    ]
