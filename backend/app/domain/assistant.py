"""Planner and prompts for the data assistant. The model never writes SQL."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.domain.llm_enrich import extract_json_value

TOOL_NAMES = frozenset(
    {
        "top_articles",
        "top_counterparties",
        "top_managers",
        "lagging_plan",
        "search_counterparties",
        "recommendations",
        "motivation",
        "fact_shipments",
        "orders",
        "realizations",
        "nomenclature",
        "quarterly_plan",
    }
)

TOOL_LABELS = {
    "top_articles": "Топ артикулов",
    "top_counterparties": "Топ клиентов",
    "top_managers": "Топ менеджеров",
    "lagging_plan": "Отстающие от плана",
    "search_counterparties": "Клиенты",
    "recommendations": "Рекомендации",
    "motivation": "Мотивация",
    "fact_shipments": "Факт отгрузок",
    "orders": "Заказы",
    "realizations": "Реализации",
    "nomenclature": "Номенклатура",
    "quarterly_plan": "План квартала",
}

MAX_TOOLS = 4
MAX_HISTORY = 6
MAX_QUESTION = 2000
PLAN_MAX_TOKENS = 220
ANSWER_MAX_TOKENS = 700

_ALLOWED_METRICS = frozenset({"sales_qty", "sales_amount", "shipment_qty", "shipment_amount"})

_TOOL_HELP = """
Инструменты (name + args). Не выдумывай имена.
- top_articles: топ артикулов. metric=sales_qty|sales_amount|shipment_qty|shipment_amount, limit=5, year, quarter, counterparty.
  sales_* = продажи Excel менеджеров; shipment_* = отгрузки 1С.
- top_counterparties: топ клиентов. те же metric/limit/year/quarter.
- top_managers: топ менеджеров по продажам Excel. limit, year, quarter.
- lagging_plan: клиенты с наименьшим % плана отгрузки. limit, year, quarter.
- search_counterparties: q=фрагмент имени.
- recommendations: подсказки правил. counterparty необязателен.
- motivation: бонусы. year, month, counterparty.
- fact_shipments: факт отгрузки тенге. year, quarter, counterparty.
- orders: заказы 1С. year, quarter, q или counterparty.
- realizations: реализации 1С. year, quarter, counterparty.
- nomenclature: q=артикул или название.
- quarterly_plan: план/факт/процент. year, quarter, counterparty.
""".strip()


def current_year_quarter(today: date) -> tuple[int, int]:
    return today.year, (today.month - 1) // 3 + 1


def months_in_quarter(quarter: int) -> list[int]:
    start = (max(1, min(4, quarter)) - 1) * 3 + 1
    return [start, start + 1, start + 2]


def clamp_limit(value: Any, default: int = 5) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(15, number))


def clamp_year(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < 2020 or number > 2035:
        return default
    return number


def clamp_quarter(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < 1 or number > 4:
        return default
    return number


def clamp_month(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number < 1 or number > 12:
        return default
    return number


def sanitize_history(raw: Optional[list[dict[str, Any]]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for row in raw or []:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").strip()
        content = str(row.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        items.append({"role": role, "content": content[:MAX_QUESTION]})
        if len(items) >= MAX_HISTORY:
            break
    return items


def sanitize_call(raw: Any, *, year: int, quarter: int) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    if name not in TOOL_NAMES:
        return None
    args_in = raw.get("args") if isinstance(raw.get("args"), dict) else {}
    args: dict[str, Any] = {
        "year": clamp_year(args_in.get("year"), year),
        "quarter": clamp_quarter(args_in.get("quarter"), quarter),
        "limit": clamp_limit(args_in.get("limit"), 5),
    }
    metric = str(args_in.get("metric") or "").strip()
    if metric in _ALLOWED_METRICS:
        args["metric"] = metric
    month = args_in.get("month")
    if month is not None:
        args["month"] = clamp_month(month, months_in_quarter(args["quarter"])[-1])
    for key in ("q", "counterparty", "article"):
        text = str(args_in.get(key) or "").strip()
        if text:
            args[key] = text[:200]
    return {"name": name, "args": args}


def parse_plan(raw: str, *, year: int, quarter: int) -> list[dict[str, Any]]:
    try:
        data = extract_json_value(raw)
    except (ValueError, TypeError):
        return []
    rows: list[Any]
    if isinstance(data, dict):
        rows = data.get("tools") if isinstance(data.get("tools"), list) else [data]
    elif isinstance(data, list):
        rows = data
    else:
        return []
    calls: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        call = sanitize_call(row, year=year, quarter=quarter)
        if not call:
            continue
        key = (call["name"], str(sorted(call["args"].items())))
        if key in seen:
            continue
        seen.add(key)
        calls.append(call)
        if len(calls) >= MAX_TOOLS:
            break
    return calls


def fallback_plan(question: str, *, year: int, quarter: int) -> list[dict[str, Any]]:
    text = (question or "").strip().lower()
    base = {"year": year, "quarter": quarter, "limit": 5}
    calls: list[dict[str, Any]] = []

    def add(name: str, **extra: Any) -> None:
        if len(calls) >= MAX_TOOLS:
            return
        if any(item["name"] == name and item["args"] == {**base, **extra} for item in calls):
            return
        calls.append({"name": name, "args": {**base, **extra}})

    ranking = any(
        token in text
        for token in ("топ", "top", "лучш", "худш", "продаваем", "популярн", "ходов", "лидер")
    )
    wants_articles = any(token in text for token in ("артикул", "sku", "номенклатур", "издели", "товар"))
    wants_clients = any(token in text for token in ("клиент", "контрагент", "магазин"))
    wants_managers = "менедж" in text
    wants_ship = any(token in text for token in ("отгруз", "реализац", "1с", "тенге"))
    wants_sales = any(token in text for token in ("продаж", "excel", "штук"))

    if ranking or wants_articles and ("топ" in text or "top" in text or "продаваем" in text):
        if wants_managers:
            add("top_managers")
        elif wants_clients and not wants_articles:
            metric = "shipment_amount" if wants_ship and not wants_sales else "sales_qty"
            add("top_counterparties", metric=metric)
        else:
            if wants_ship and not wants_sales:
                add("top_articles", metric="shipment_qty")
            elif wants_ship and wants_sales:
                add("top_articles", metric="sales_qty")
                add("top_articles", metric="shipment_qty")
            else:
                add("top_articles", metric="sales_qty")
                if not wants_articles:
                    add("top_counterparties", metric="sales_qty")

    if any(token in text for token in ("отста", "план", "выполнен")):
        add("lagging_plan")
        add("quarterly_plan")
    if "рекоменд" in text or "что делать" in text:
        add("recommendations")
    if "мотивац" in text or "бонус" in text:
        add("motivation")
    if "заказ" in text:
        add("orders")
    if "реализац" in text or ("отгруз" in text and not ranking):
        add("realizations")
        add("fact_shipments")
    if "номенклатур" in text or "артикул" in text and not ranking:
        add("nomenclature", q=question[:120])
    if "контрагент" in text or "клиент" in text and not ranking:
        add("search_counterparties", q=question[:120])

    if not calls:
        add("top_articles", metric="sales_qty")
        add("search_counterparties", q=question[:120])
    return calls[:MAX_TOOLS]


def build_plan_messages(
    question: str,
    *,
    year: int,
    quarter: int,
    history: Optional[list[dict[str, str]]] = None,
) -> list[dict[str, str]]:
    system = (
        "Ты маршрутизатор аналитики ювелирного сервиса. "
        "Верни ТОЛЬКО JSON вида {\"tools\":[{\"name\":\"top_articles\",\"args\":{...}}]}. "
        f"Не больше {MAX_TOOLS} инструментов. Период по умолчанию {year} Q{quarter}. "
        "Если спрашивают топ артикулов без уточнения источника — два вызова: sales_qty и shipment_qty. "
        "Если явно продажи Excel — только sales_qty. Если явно отгрузка/1С — только shipment_*. "
        "Если в вопросе есть клиент — добавь quarterly_plan и recommendations с его именем. "
        "Не отвечай на вопрос текстом.\n"
        f"{_TOOL_HELP}"
    )
    turns = ""
    for item in history or []:
        turns += f"{item['role']}: {item['content']}\n"
    user = f"{turns}Вопрос: {question}".strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_answer_messages(
    question: str,
    facts: list[dict[str, Any]],
    *,
    year: int,
    quarter: int,
    history: Optional[list[dict[str, str]]] = None,
) -> list[dict[str, str]]:
    system = (
        "Ты аналитик ювелирной сети. Отвечай по-русски коротко, как живому менеджеру: "
        "сначала вывод, потом 3–7 фактов цифрами, в конце что сделать. "
        f"Период фактов: {year} Q{quarter}, если в фактах не сказано иное. "
        "Продажи Excel (sales_*) и отгрузки 1С (shipment_*) — разные источники, не смешивай. "
        "Цифры только из JSON фактов. Нет строки в фактах — скажи, что данных нет. "
        "Не выдумывай артикулы, суммы и клиентов. Не предлагай править 1С из чата."
    )
    turns = ""
    for item in history or []:
        turns += f"{item['role']}: {item['content']}\n"
    user = (
        f"{turns}Вопрос: {question}\nФакты:\n"
        f"{_facts_json(facts)}"
    ).strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _facts_json(facts: list[dict[str, Any]]) -> str:
    import json

    return json.dumps(facts, ensure_ascii=False, default=str)[:8000]


def expand_plan(
    calls: list[dict[str, Any]],
    *,
    question: str,
    year: int,
    quarter: int,
) -> list[dict[str, Any]]:
    """Add the paired sales/shipment top and client plan/recs when there is room."""
    text = (question or "").strip().lower()
    wants_ship = any(token in text for token in ("отгруз", "реализац", "1с", "тенге"))
    wants_sales = any(token in text for token in ("продаж", "excel", "штук"))
    exclusive = (wants_ship and not wants_sales) or (wants_sales and not wants_ship)
    out = [dict(call, args=dict(call.get("args") or {})) for call in calls]
    seen = {(item["name"], str(sorted(item["args"].items()))) for item in out}

    def add(name: str, **extra: Any) -> None:
        if len(out) >= MAX_TOOLS:
            return
        seed = out[0]["args"] if out else {"year": year, "quarter": quarter, "limit": 5}
        args = {
            "year": seed.get("year", year),
            "quarter": seed.get("quarter", quarter),
            "limit": seed.get("limit", 5),
            **extra,
        }
        if seed.get("counterparty") and "counterparty" not in args:
            args["counterparty"] = seed["counterparty"]
        key = (name, str(sorted(args.items())))
        if key in seen:
            return
        seen.add(key)
        out.append({"name": name, "args": args})

    article_metrics = {item["args"].get("metric") for item in out if item["name"] == "top_articles"}
    if article_metrics and not exclusive:
        if "sales_qty" in article_metrics and "shipment_qty" not in article_metrics:
            add("top_articles", metric="shipment_qty")
        elif "shipment_qty" in article_metrics and "sales_qty" not in article_metrics:
            add("top_articles", metric="sales_qty")

    counterparty = next((item["args"].get("counterparty") for item in out if item["args"].get("counterparty")), None)
    if counterparty:
        if not any(item["name"] == "quarterly_plan" for item in out):
            add("quarterly_plan", counterparty=counterparty)
        if not any(item["name"] == "recommendations" for item in out):
            add("recommendations", counterparty=counterparty)
    return out[:MAX_TOOLS]


def attach_rank_change(
    rows: list[dict[str, Any]],
    previous: list[dict[str, Any]],
    *,
    key: str,
) -> list[dict[str, Any]]:
    prev_rank: dict[Any, int] = {}
    prev_row: dict[Any, dict[str, Any]] = {}
    for index, row in enumerate(previous):
        ident = row.get(key)
        if ident in (None, "") or ident in prev_rank:
            continue
        prev_rank[ident] = index
        prev_row[ident] = row
    enriched: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        item = dict(row)
        item["rank"] = index + 1
        ident = item.get(key)
        if ident in prev_rank:
            item["prev_rank"] = prev_rank[ident] + 1
            item["rank_delta"] = prev_rank[ident] - index
            older = prev_row[ident]
            item["prev_quantity"] = older.get("quantity")
            item["prev_amount"] = older.get("amount")
        elif previous:
            item["is_new"] = True
        enriched.append(item)
    return enriched


_METRIC_CARD_TITLE = {
    "sales_qty": "Топ · продажи Excel, шт",
    "sales_amount": "Топ · продажи Excel, тенге",
    "shipment_qty": "Топ · отгрузки 1С, шт",
    "shipment_amount": "Топ · отгрузки 1С, тенге",
}


def _card_rows(block: dict[str, Any]) -> list[dict[str, Any]]:
    tool = block.get("tool")
    raw = block.get("rows") or block.get("clients") or block.get("items") or []
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw[:8]):
        if not isinstance(row, dict):
            continue
        article = str(row.get("article") or "").strip()
        counterparty = str(row.get("counterparty") or "").strip()
        if not counterparty and tool == "search_counterparties":
            counterparty = str(row.get("name") or "").strip()
        manager = str(row.get("manager") or "").strip()
        title = article or counterparty or manager or str(row.get("number") or row.get("title") or "").strip()
        if not title:
            continue
        rank = int(row.get("rank") or index + 1)
        prompt = ""
        if article:
            prompt = f"Разбор артикула {article} за текущий квартал: продажи Excel и отгрузки 1С"
        elif counterparty:
            prompt = f"Рекомендации и план по клиенту {counterparty}"
        elif manager:
            prompt = f"Топ клиентов менеджера {manager} за текущий квартал"
        hint = ""
        if article:
            hint = str(row.get("name") or row.get("wear_type") or "").strip()
        else:
            hint = str(row.get("message") or row.get("wear_type") or "").strip()
        amount = row.get("amount")
        if amount is None:
            amount = row.get("fact", row.get("bonus"))
        rows.append(
            {
                "rank": rank,
                "title": title,
                "hint": hint or None,
                "quantity": row.get("quantity"),
                "amount": amount,
                "percent": row.get("percent"),
                "rank_delta": row.get("rank_delta"),
                "prev_rank": row.get("prev_rank"),
                "is_new": bool(row.get("is_new")),
                "prompt": prompt,
                "tool": tool,
            }
        )
    return rows


def fact_cards(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for block in facts:
        if not isinstance(block, dict) or block.get("error"):
            continue
        rows = _card_rows(block)
        if not rows:
            continue
        metric = str(block.get("metric") or "")
        title = _METRIC_CARD_TITLE.get(metric) or str(block.get("label") or TOOL_LABELS.get(str(block.get("tool") or ""), "Срез"))
        if block.get("counterparty"):
            title = f"{title} · {block['counterparty']}"
        cards.append(
            {
                "tool": block.get("tool"),
                "title": title,
                "period": block.get("period"),
                "rows": rows,
            }
        )
    return cards[:4]


def follow_ups_from_facts(facts: list[dict[str, Any]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(label: str, prompt: str) -> None:
        text = prompt.strip()
        if not text or text in seen or len(items) >= 3:
            return
        seen.add(text)
        items.append({"label": label, "prompt": text})

    tools = {str(block.get("tool")) for block in facts}
    metrics = {str(block.get("metric")) for block in facts}
    if "top_articles" in tools:
        if "sales_qty" in metrics and "shipment_qty" not in metrics:
            add("Топ по отгрузке 1С", "Топ-5 артикулов по отгрузке 1С за текущий квартал")
        if "shipment_qty" in metrics and "sales_qty" not in metrics:
            add("Топ по продажам", "Топ-5 продаваемых артикулов за текущий квартал")
    for block in facts:
        if not isinstance(block, dict):
            continue
        for row in block.get("rows") or []:
            if not isinstance(row, dict):
                continue
            article = str(row.get("article") or "").strip()
            if article:
                add(f"Разбор {article}", f"Разбор артикула {article} за текущий квартал: продажи Excel и отгрузки 1С")
                break
        for row in block.get("rows") or block.get("clients") or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("counterparty") or "").strip()
            if name:
                add("План и рекомендации", f"Рекомендации и план по клиенту {name}")
                break
    if "lagging_plan" not in tools:
        add("Отстают от плана", "Кто сильнее всего отстаёт от квартального плана отгрузки?")
    return items


def template_answer(facts: list[dict[str, Any]]) -> str:
    cards = fact_cards(facts)
    if not cards:
        return "За этот период в доступных данных пусто. Смените вопрос или дождитесь синхронизации."
    lines = ["Срез из отчётов сервиса."]
    for card in cards[:2]:
        lines.append(str(card.get("title") or "Срез") + ":")
        for row in card.get("rows") or []:
            piece = f"{row.get('rank')}. {row.get('title')}"
            if row.get("quantity") is not None:
                piece += f" — {row['quantity']} шт"
            if row.get("amount") is not None:
                piece += f", {row['amount']}"
            if row.get("percent") is not None:
                piece += f" ({row['percent']}%)"
            lines.append(piece)
    return "\n".join(lines)
