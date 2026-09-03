from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


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


@dataclass
class PriceArbitrageAlert:
    counterparty: str
    wear_type: str
    shipment_avg_price: Decimal
    client_avg_price: Decimal


def illiquid_recommendations(
    items: list[IlliquidCandidate],
    *,
    turnover_threshold: Decimal = Decimal(10),
    dwell_months: int = 6,
    max_share: Decimal = Decimal("0.10"),
) -> list[dict]:
    low = [i for i in items if i.avg_turnover < turnover_threshold or i.months_without_sales > dwell_months]
    total_stock = sum((i.stock_qty for i in items), Decimal(0))
    limit = total_stock * max_share if total_stock else Decimal(0)
    selected: list[IlliquidCandidate] = []
    used = Decimal(0)
    for item in sorted(low, key=lambda x: x.avg_turnover):
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
            reason.append(f"пролежка {item.months_without_sales} мес.")
        result.append(
            {
                "type": "illiquid",
                "severity": "high" if item.months_without_sales > dwell_months else "medium",
                "counterparty": item.counterparty,
                "article": item.article,
                "message": (
                    f"Рекомендация к возврату/обмену артикула {item.article} "
                    f"({', '.join(reason)}). Лимит изъятия ≤10%."
                ),
                "details": {
                    "wear_type": item.wear_type,
                    "lts": item.lts,
                    "metal_color": item.metal_color,
                    "avg_turnover": str(item.avg_turnover),
                },
            }
        )
    return result


def successful_pattern_recommendations(patterns: list[PatternHit], top_n: int = 10) -> list[dict]:
    ranked = sorted(patterns, key=lambda p: p.sales, reverse=True)[:top_n]
    return [
        {
            "type": "pattern",
            "severity": "info",
            "counterparty": p.counterparty,
            "article": None,
            "message": (
                f"Клиент хорошо продаёт связку «{p.wear_type} / {p.lts} / {p.metal_color}». "
                f"Рекомендация на подсортировку (продажи {p.sales})."
            ),
            "details": {"sales": str(p.sales)},
        }
        for p in ranked
    ]


def price_arbitrage_recommendations(alerts: list[PriceArbitrageAlert]) -> list[dict]:
    out = []
    for a in alerts:
        if a.client_avg_price >= a.shipment_avg_price:
            continue
        out.append(
            {
                "type": "price_arbitrage",
                "severity": "high",
                "counterparty": a.counterparty,
                "article": None,
                "message": (
                    f"Внимание! Клиент продаёт [{a.wear_type}] ниже нашей отгрузочной цены. "
                    f"Рекомендуемая цена для будущих отгрузок: не выше {a.client_avg_price} тенге."
                ),
                "details": {
                    "shipment_avg_price": str(a.shipment_avg_price),
                    "client_avg_price": str(a.client_avg_price),
                    "wear_type": a.wear_type,
                },
            }
        )
    return out
