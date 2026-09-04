from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

CBR_DAILY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
CBR_DYNAMIC_URL = "https://www.cbr.ru/scripts/XML_dynamic.asp"
CBR_USER_AGENT = "kz-ai-analytics/1.0"
CACHE_TTL_SEC = 3600
HISTORY_DAYS = 45

# Official CBR internal IDs (VAL_NM_RQ).
CBR_CURRENCIES: tuple[tuple[str, str, str], ...] = (
    ("USD", "R01235", "Доллар США"),
    ("EUR", "R01239", "Евро"),
    ("KZT", "R01335", "Тенге"),
)

Fetcher = Callable[[str], str]

_cache_lock = threading.Lock()
_cache: tuple[float, dict[str, Any]] | None = None


def parse_cbr_decimal(raw: str | None) -> Decimal:
    text = (raw or "").strip().replace(" ", "").replace(",", ".")
    if not text:
        raise InvalidOperation("empty")
    return Decimal(text)


def parse_cbr_date(raw: str | None) -> date | None:
    text = (raw or "").strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _child_text(el: ET.Element, tag: str) -> str:
    node = el.find(tag)
    if node is None or node.text is None:
        return ""
    return node.text


def parse_daily_xml(xml: str) -> tuple[date | None, dict[str, dict[str, Any]]]:
    root = ET.fromstring(xml)
    as_of = parse_cbr_date(root.attrib.get("Date"))
    by_code: dict[str, dict[str, Any]] = {}
    for valute in root.findall("Valute"):
        code = _child_text(valute, "CharCode").strip().upper()
        if not code:
            continue
        nominal = parse_cbr_decimal(_child_text(valute, "Nominal") or "1")
        value = parse_cbr_decimal(_child_text(valute, "Value"))
        unit_raw = _child_text(valute, "VunitRate")
        unit = parse_cbr_decimal(unit_raw) if unit_raw else (value / nominal)
        by_code[code] = {
            "id": valute.attrib.get("ID") or "",
            "name": _child_text(valute, "Name").strip(),
            "nominal": nominal,
            "rate": unit,
        }
    return as_of, by_code


def parse_dynamic_xml(xml: str) -> list[tuple[date, Decimal]]:
    root = ET.fromstring(xml)
    rows: list[tuple[date, Decimal]] = []
    for rec in root.findall("Record"):
        day = parse_cbr_date(rec.attrib.get("Date"))
        if day is None:
            continue
        nominal = parse_cbr_decimal(_child_text(rec, "Nominal") or "1")
        unit_raw = _child_text(rec, "VunitRate")
        if unit_raw:
            rate = parse_cbr_decimal(unit_raw)
        else:
            rate = parse_cbr_decimal(_child_text(rec, "Value")) / nominal
        rows.append((day, rate))
    rows.sort(key=lambda item: item[0])
    return rows


def change_percent(current: Decimal, previous: Decimal | None) -> Decimal | None:
    if previous is None or previous == 0:
        return None
    return ((current - previous) / previous * Decimal("100")).quantize(Decimal("0.01"))


def _decode_cbr_bytes(raw: bytes) -> str:
    head = raw[:120].upper()
    if b"ENCODING=\"UTF-8\"" in head or b"ENCODING='UTF-8'" in head:
        return raw.decode("utf-8", errors="replace")
    return raw.decode("windows-1251", errors="replace")


def default_fetch(url: str, *, client: Optional[httpx.Client] = None) -> str:
    own = client is None
    http = client or httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": CBR_USER_AGENT},
    )
    try:
        resp = http.get(url)
        resp.raise_for_status()
        return _decode_cbr_bytes(resp.content)
    finally:
        if own:
            http.close()


def _dynamic_url(valute_id: str, start: date, end: date) -> str:
    return (
        f"{CBR_DYNAMIC_URL}"
        f"?date_req1={start.strftime('%d/%m/%Y')}"
        f"&date_req2={end.strftime('%d/%m/%Y')}"
        f"&VAL_NM_RQ={valute_id}"
    )


def build_cbr_rates(daily_xml: str, history_xml_by_code: dict[str, str]) -> dict[str, Any]:
    as_of, daily = parse_daily_xml(daily_xml)
    items: list[dict[str, Any]] = []
    for code, valute_id, fallback_name in CBR_CURRENCIES:
        spot = daily.get(code)
        history_xml = history_xml_by_code.get(code, "")
        history = parse_dynamic_xml(history_xml) if history_xml else []
        if spot:
            last_day = as_of or (history[-1][0] if history else None)
            last_rate = spot["rate"]
            if last_day and (not history or history[-1][0] != last_day):
                history.append((last_day, last_rate))
            name = spot["name"] or fallback_name
        elif history:
            last_day, last_rate = history[-1]
            name = fallback_name
        else:
            continue
        prev = history[-2][1] if len(history) >= 2 else None
        items.append(
            {
                "code": code,
                "name": name,
                "rate": last_rate,
                "change_percent": change_percent(last_rate, prev),
                "history": [{"date": day.isoformat(), "rate": rate} for day, rate in history],
            }
        )
    return {"as_of": as_of, "status": "ok" if items else "error", "source": "cbr", "items": items}


def _load_cbr_rates(fetch: Fetcher) -> dict[str, Any]:
    daily_xml = fetch(CBR_DAILY_URL)
    end = date.today()
    start = end - timedelta(days=HISTORY_DAYS)
    history_xml_by_code: dict[str, str] = {}
    as_of, daily = parse_daily_xml(daily_xml)
    for code, default_id, _name in CBR_CURRENCIES:
        valute_id = (daily.get(code) or {}).get("id") or default_id
        history_xml_by_code[code] = fetch(_dynamic_url(valute_id, start, end))
    payload = build_cbr_rates(daily_xml, history_xml_by_code)
    if as_of:
        payload["as_of"] = as_of
    return payload


def get_cbr_rates(*, fetch: Fetcher | None = None, force: bool = False) -> dict[str, Any]:
    global _cache
    now = time.monotonic()
    with _cache_lock:
        if not force and _cache and now - _cache[0] < CACHE_TTL_SEC:
            return _cache[1]
    loader = fetch or default_fetch
    try:
        payload = _load_cbr_rates(loader)
    except Exception:  # noqa: BLE001
        logger.exception("CBR rates fetch failed")
        with _cache_lock:
            if _cache:
                stale = dict(_cache[1])
                stale["status"] = "stale"
                return stale
        return {"as_of": None, "status": "error", "source": "cbr", "items": []}
    with _cache_lock:
        _cache = (now, payload)
    return payload
