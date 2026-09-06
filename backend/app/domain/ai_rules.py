from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

PATTERN_STOCK_COVER = Decimal("0.30")
MIN_PATTERN_SALES = Decimal(3)
MIN_RETURN_QTY = Decimal(2)
MIN_PRICE_SAMPLES = 3
MIN_PRICE_GAP = Decimal("0.05")


@dataclass
class IlliquidCandidate:
    counterparty: str
    article: str
    wear_type: Optional[str]
    lts: Optional[str]
    metal_color: Optional[str]
    avg_turnover: Decimal
    stock_qty: Decimal
    months_without_sales: int


@dataclass
class PatternHit:
    counterparty: str
    wear_type: str
    lts: str
    metal_color: str
    sales: Decimal
    stock_qty: Decimal = Decimal(0)


@dataclass
class PriceArbitrageAlert:
    counterparty: str
    wear_type: str
    shipment_avg_price: Decimal
    client_avg_price: Decimal
    sample_count: int = 3


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def has_bundle_attrs(wear: Optional[str], lts: Optional[str], color: Optional[str]) -> bool:
    return any(bool(part) and part != "—" for part in (wear, lts, color))


def is_exit_lts(lts: Optional[str]) -> bool:
    return "вывод" in (lts or "").strip().lower()


def suggested_restock_qty(hit: PatternHit) -> Decimal:
    gap = hit.sales - hit.stock_qty
    return gap if gap > 0 else Decimal(0)


def bundle_label(wear: Optional[str], lts: Optional[str], color: Optional[str]) -> str:
    parts = [part for part in (wear, lts, color) if part and part != "—"]
    return " / ".join(parts) if parts else "без характеристик 1С"


def qty_label(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def score_illiquid(item: IlliquidCandidate) -> int:
    dwell = min(45.0, float(item.months_without_sales) * 5.0)
    turnover_gap = 0.0
    if item.avg_turnover < Decimal(10):
        turnover_gap = float((Decimal(10) - item.avg_turnover) * Decimal(3))
    stock = min(25.0, float(item.stock_qty) * 0.5)
    return clamp_score(dwell + turnover_gap + stock)


def score_pattern(hit: PatternHit) -> int:
    sales = float(hit.sales)
    stock = float(hit.stock_qty)
    coverage = (stock / sales) if sales else 1.0
    urgency = (1.0 - min(coverage, 1.0)) * 50
    volume = min(40.0, sales * 0.4)
    return clamp_score(urgency + volume)


def score_price(alert: PriceArbitrageAlert) -> int:
    if alert.shipment_avg_price <= 0:
        return 50
    gap = float((alert.shipment_avg_price - alert.client_avg_price) / alert.shipment_avg_price)
    return clamp_score(40 + max(gap, 0.0) * 120)


def score_mix(months: int, weak_stock: Decimal, strong_sales: Decimal) -> int:
    return clamp_score(50 + months * 4 + min(20.0, float(weak_stock)) + min(10.0, float(strong_sales) * 0.1))


def needs_restock(hit: PatternHit, cover: Decimal = PATTERN_STOCK_COVER) -> bool:
    if not has_bundle_attrs(hit.wear_type, hit.lts, hit.metal_color):
        return False
    if is_exit_lts(hit.lts):
        return False
    if hit.sales < MIN_PATTERN_SALES:
        return False
    if suggested_restock_qty(hit) <= 0:
        return False
    return hit.stock_qty < hit.sales * cover


def dedupe_recommendations(items: list[dict]) -> list[dict]:
    mix_keys = {
        (item.get("counterparty"), item.get("article"))
        for item in items
        if item.get("type") == "mix" and item.get("article")
    }
    return [
        item
        for item in items
        if not (item.get("type") == "illiquid" and (item.get("counterparty"), item.get("article")) in mix_keys)
    ]


def rank_recommendations(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: (-int(item.get("score") or 0), str(item.get("type") or "")))


def ru_count(n: int, one: str, few: str, many: str) -> str:
    abs_n = abs(n) % 100
    if 11 <= abs_n <= 14:
        word = many
    else:
        last = abs_n % 10
        if last == 1:
            word = one
        elif 2 <= last <= 4:
            word = few
        else:
            word = many
    return f"{n} {word}"


def build_recommendations_summary(items: list[dict]) -> str:
    if not items:
        return "Сигналов нет. Нужны продажи, остатки и участники акции ★."
    actions = {"return": 0, "restock": 0, "reprice": 0}
    for item in items:
        key = item.get("action")
        if key in actions:
            actions[key] += 1
    parts = [f"Вижу {ru_count(len(items), 'сигнал', 'сигнала', 'сигналов')}."]
    bits = []
    if actions["return"]:
        bits.append(f"к возврату — {actions['return']}")
    if actions["restock"]:
        bits.append(f"к подсортировке — {actions['restock']}")
    if actions["reprice"]:
        bits.append(f"по цене — {actions['reprice']}")
    if bits:
        parts.append("Из них " + ", ".join(bits) + ".")
    top = items[0]
    who = top.get("counterparty") or "клиент"
    title = top.get("title") or "разберите приоритетный кейс"
    parts.append(f"Первым делом: {who} — {title}.")
    return " ".join(parts)


def _illiquid_for_client(
    items: list[IlliquidCandidate],
    *,
    turnover_threshold: Decimal,
    dwell_months: int,
    max_share: Decimal,
) -> list[dict]:
    low = [
        item
        for item in items
        if item.stock_qty >= MIN_RETURN_QTY
        and (item.avg_turnover < turnover_threshold or item.months_without_sales > dwell_months)
    ]
    total_stock = sum((item.stock_qty for item in items), Decimal(0))
    limit = total_stock * max_share if total_stock else Decimal(0)
    selected: list[IlliquidCandidate] = []
    used = Decimal(0)
    for item in sorted(low, key=lambda row: row.avg_turnover):
        if used + item.stock_qty > limit and limit > 0:
            continue
        selected.append(item)
        used += item.stock_qty

    result = []
    for item in selected:
        reason = []
        if item.avg_turnover < turnover_threshold:
            reason.append(f"ср. об-ть {item.avg_turnover:.2f}% < 10%")
        if item.months_without_sales > dwell_months:
            reason.append(f"залежалый товар {item.months_without_sales} мес.")
        qty = qty_label(item.stock_qty)
        result.append(
            {
                "type": "illiquid",
                "severity": "high" if item.months_without_sales > dwell_months else "medium",
                "action": "return",
                "title": f"Верните {qty} шт. {item.article}",
                "score": score_illiquid(item),
                "counterparty": item.counterparty,
                "article": item.article,
                "message": (
                    f"Верните {qty} шт. артикула {item.article} "
                    f"({', '.join(reason)}). Не больше 10% остатка этого клиента за раз."
                ),
                "details": {
                    "wear_type": item.wear_type,
                    "lts": item.lts,
                    "metal_color": item.metal_color,
                    "avg_turnover": str(item.avg_turnover),
                    "stock_qty": str(item.stock_qty),
                    "suggest_qty": str(item.stock_qty),
                    "months_without_sales": item.months_without_sales,
                },
            }
        )
    return result


def illiquid_recommendations(
    items: list[IlliquidCandidate],
    *,
    turnover_threshold: Decimal = Decimal(10),
    dwell_months: int = 6,
    max_share: Decimal = Decimal("0.10"),
) -> list[dict]:
    by_client: dict[str, list[IlliquidCandidate]] = {}
    for item in items:
        by_client.setdefault(item.counterparty, []).append(item)
    result: list[dict] = []
    for group in by_client.values():
        result.extend(
            _illiquid_for_client(
                group,
                turnover_threshold=turnover_threshold,
                dwell_months=dwell_months,
                max_share=max_share,
            )
        )
    return result


def successful_pattern_recommendations(patterns: list[PatternHit], top_n: int = 10) -> list[dict]:
    ranked = [hit for hit in sorted(patterns, key=lambda p: p.sales, reverse=True) if needs_restock(hit)]
    ranked = ranked[:top_n]
    return [
        {
            "type": "pattern",
            "severity": "info",
            "action": "restock",
            "title": f"Довезите {qty_label(suggested_restock_qty(p))} шт. {bundle_label(p.wear_type, p.lts, p.metal_color)}",
            "score": score_pattern(p),
            "counterparty": p.counterparty,
            "article": None,
            "message": (
                f"Довезите {qty_label(suggested_restock_qty(p))} шт. связки "
                f"«{bundle_label(p.wear_type, p.lts, p.metal_color)}» "
                f"(продажи {qty_label(p.sales)}, остаток {qty_label(p.stock_qty)})."
            ),
            "details": {
                "sales": str(p.sales),
                "stock_qty": str(p.stock_qty),
                "suggest_qty": str(suggested_restock_qty(p)),
            },
        }
        for p in ranked
    ]


def price_arbitrage_recommendations(alerts: list[PriceArbitrageAlert]) -> list[dict]:
    out = []
    for a in alerts:
        if not has_bundle_attrs(a.wear_type, None, None):
            continue
        if a.sample_count < MIN_PRICE_SAMPLES:
            continue
        if a.shipment_avg_price <= 0 or a.client_avg_price >= a.shipment_avg_price:
            continue
        gap = (a.shipment_avg_price - a.client_avg_price) / a.shipment_avg_price
        if gap < MIN_PRICE_GAP:
            continue
        out.append(
            {
                "type": "price_arbitrage",
                "severity": "high",
                "action": "reprice",
                "title": f"Снизить цену отгрузки · {a.wear_type}",
                "score": score_price(a),
                "counterparty": a.counterparty,
                "article": None,
                "message": (
                    f"Клиент продаёт [{a.wear_type}] ниже отгрузки на {gap * 100:.0f}%. "
                    f"Цена следующих отгрузок: не выше {qty_label(a.client_avg_price)} тенге."
                ),
                "details": {
                    "shipment_avg_price": str(a.shipment_avg_price),
                    "client_avg_price": str(a.client_avg_price),
                    "wear_type": a.wear_type,
                    "gap_percent": f"{gap * 100:.1f}",
                    "sample_count": a.sample_count,
                },
            }
        )
    return out


def mix_imbalance_recommendations(
    patterns: list[PatternHit],
    stocks: list[IlliquidCandidate],
    *,
    dwell_months: int = 6,
) -> list[dict]:
    by_pattern: dict[str, list[PatternHit]] = {}
    by_stock: dict[str, list[IlliquidCandidate]] = {}
    for hit in patterns:
        by_pattern.setdefault(hit.counterparty, []).append(hit)
    for item in stocks:
        by_stock.setdefault(item.counterparty, []).append(item)

    result = []
    for counterparty, hits in by_pattern.items():
        best = max(hits, key=lambda hit: hit.sales)
        if not has_bundle_attrs(best.wear_type, best.lts, best.metal_color):
            continue
        if best.sales < MIN_PATTERN_SALES:
            continue
        best_key = (best.wear_type, best.lts, best.metal_color)
        weak = [
            item
            for item in by_stock.get(counterparty, [])
            if (item.wear_type or "—", item.lts or "—", item.metal_color or "—") != best_key
            and item.months_without_sales > dwell_months
            and item.stock_qty > 0
        ]
        if not weak:
            continue
        worst = max(weak, key=lambda item: (item.months_without_sales, item.stock_qty))
        result.append(
            {
                "type": "mix",
                "severity": "high" if worst.months_without_sales >= 8 else "medium",
                "action": "return",
                "title": f"Верните {qty_label(worst.stock_qty)} шт. и довезите ходовое",
                "score": score_mix(worst.months_without_sales, worst.stock_qty, best.sales),
                "counterparty": counterparty,
                "article": worst.article,
                "message": (
                    f"Верните {qty_label(worst.stock_qty)} шт. {worst.article} "
                    f"({bundle_label(worst.wear_type, worst.lts, worst.metal_color)}, "
                    f"{worst.months_without_sales} мес. без продаж) и довезите "
                    f"«{bundle_label(best.wear_type, best.lts, best.metal_color)}» "
                    f"(продажи {qty_label(best.sales)} шт.)."
                ),
                "details": {
                    "strong_bundle": bundle_label(best.wear_type, best.lts, best.metal_color),
                    "strong_sales": str(best.sales),
                    "weak_article": worst.article,
                    "weak_bundle": bundle_label(worst.wear_type, worst.lts, worst.metal_color),
                    "weak_stock": str(worst.stock_qty),
                    "suggest_qty": str(worst.stock_qty),
                    "months_without_sales": worst.months_without_sales,
                },
            }
        )
    return result
