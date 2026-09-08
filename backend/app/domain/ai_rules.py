from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

PATTERN_STOCK_COVER = Decimal("0.30")
RESTOCK_TARGET_COVER = Decimal("0.50")
RESTOCK_PER_CLIENT = 3
RECENT_MONTHS = 3
MIN_PATTERN_SALES = Decimal(3)
MIN_RETURN_QTY = Decimal(2)
MIN_PRICE_SAMPLES = 3
MIN_PRICE_GAP = Decimal("0.05")
EXIT_LTS_SCORE_BOOST = 15
PLAN_BEHIND_PERCENT = Decimal(50)
PLAN_SCORE_BOOST = 12


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
    recent_sales: Optional[Decimal] = None


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


def is_recent_month(year: Optional[int], month: Optional[int], as_of: date, window: int = RECENT_MONTHS) -> bool:
    if not year or not month:
        return False
    as_of_idx = as_of.year * 12 + as_of.month
    idx = int(year) * 12 + int(month)
    return as_of_idx - window + 1 <= idx <= as_of_idx


def pattern_velocity(hit: PatternHit) -> Decimal:
    return hit.recent_sales if hit.recent_sales is not None else hit.sales


def bundle_key(wear: Optional[str], lts: Optional[str], color: Optional[str]) -> tuple[str, str, str]:
    return (wear or "—", lts or "—", color or "—")


def suggested_restock_qty(hit: PatternHit) -> Decimal:
    target = pattern_velocity(hit) * RESTOCK_TARGET_COVER
    gap = target - hit.stock_qty
    if gap <= 0:
        return Decimal(0)
    return Decimal(1) if gap < 1 else gap


def bundle_label(wear: Optional[str], lts: Optional[str], color: Optional[str]) -> str:
    parts = [part for part in (wear, lts, color) if part and part != "—"]
    return " / ".join(parts) if parts else "без характеристик 1С"


def qty_label(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if quantized == quantized.to_integral_value():
        quantized = quantized.to_integral_value()
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def money_label(value: Decimal) -> str:
    whole = int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{whole:,}".replace(",", " ")


def score_illiquid(item: IlliquidCandidate) -> int:
    dwell = min(45.0, float(item.months_without_sales) * 5.0)
    turnover_gap = 0.0
    if item.avg_turnover < Decimal(10):
        turnover_gap = float((Decimal(10) - item.avg_turnover) * Decimal(3))
    stock = min(25.0, float(item.stock_qty) * 0.5)
    exit_bonus = float(EXIT_LTS_SCORE_BOOST) if is_exit_lts(item.lts) else 0.0
    return clamp_score(dwell + turnover_gap + stock + exit_bonus)


def score_pattern(hit: PatternHit) -> int:
    sales = float(pattern_velocity(hit))
    stock = float(hit.stock_qty)
    coverage = (stock / sales) if sales else 1.0
    urgency = (1.0 - min(coverage, 1.0)) * 50
    volume = min(40.0, sales * 0.4)
    return clamp_score(urgency + volume)


def score_price(alert: PriceArbitrageAlert) -> int:
    if not alert.shipment_avg_price.is_finite() or alert.shipment_avg_price <= 0:
        return 50
    if not alert.client_avg_price.is_finite():
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
    recent = pattern_velocity(hit)
    if recent < MIN_PATTERN_SALES:
        return False
    if suggested_restock_qty(hit) <= 0:
        return False
    return hit.stock_qty < recent * cover


def apply_plan_boost(items: list[dict], plan_percents: Optional[dict[str, Decimal]] = None) -> list[dict]:
    if not plan_percents:
        return items
    for item in items:
        details = dict(item.get("details") or {})
        names = [item.get("counterparty"), details.get("to_counterparty")]
        behind = False
        shown: Optional[Decimal] = None
        for name in names:
            if not name:
                continue
            pct = plan_percents.get(str(name))
            if pct is None:
                continue
            if shown is None:
                shown = pct
            if pct < PLAN_BEHIND_PERCENT:
                behind = True
                shown = pct
        if shown is not None:
            details["plan_percent"] = f"{shown.quantize(Decimal('0.1'))}"
            item["details"] = details
        if behind:
            item["score"] = clamp_score(int(item.get("score") or 0) + PLAN_SCORE_BOOST)
            item["details"] = details
    return items


def dedupe_recommendations(items: list[dict]) -> list[dict]:
    mix_keys = {
        (item.get("counterparty"), item.get("article"))
        for item in items
        if item.get("type") == "mix" and item.get("article")
    }
    transfer_articles = {
        (item.get("counterparty"), item.get("article"))
        for item in items
        if item.get("type") == "transfer" and item.get("article")
    }
    transfer_need = {
        (str((item.get("details") or {}).get("to_counterparty") or ""), str((item.get("details") or {}).get("bundle") or ""))
        for item in items
        if item.get("type") == "transfer"
    }
    out = []
    for item in items:
        kind = item.get("type")
        key = (item.get("counterparty"), item.get("article"))
        if kind == "illiquid" and (key in mix_keys or key in transfer_articles):
            continue
        if kind == "mix" and key in transfer_articles:
            continue
        if kind == "pattern":
            bundle = str((item.get("details") or {}).get("bundle") or "")
            if (str(item.get("counterparty") or ""), bundle) in transfer_need:
                continue
        out.append(item)
    return out


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
    actions = {"return": 0, "restock": 0, "reprice": 0, "transfer": 0}
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
    if actions["transfer"]:
        bits.append(f"к перекладке — {actions['transfer']}")
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
        qty = qty_label(item.stock_qty)
        bits = [f"Верните {qty} шт. {item.article}"]
        if item.avg_turnover < turnover_threshold:
            bits.append(f"об-ть {qty_label(item.avg_turnover)}%")
        if item.months_without_sales > dwell_months:
            bits.append(f"{item.months_without_sales} мес. без продаж")
        result.append(
            {
                "type": "illiquid",
                "severity": "high" if item.months_without_sales > dwell_months else "medium",
                "action": "return",
                "title": f"Верните {qty} шт. {item.article}",
                "score": score_illiquid(item),
                "counterparty": item.counterparty,
                "article": item.article,
                "message": " · ".join(bits),
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


def _pattern_payload(p: PatternHit) -> dict:
    qty = suggested_restock_qty(p)
    bundle = bundle_label(p.wear_type, p.lts, p.metal_color)
    recent = pattern_velocity(p)
    window = "за 3 мес. " if p.recent_sales is not None else ""
    return {
        "type": "pattern",
        "severity": "info",
        "action": "restock",
        "title": f"Довезите {qty_label(qty)} шт. {bundle}",
        "score": score_pattern(p),
        "counterparty": p.counterparty,
        "article": None,
        "message": (
            f"Довезите {qty_label(qty)} шт. связки «{bundle}» "
            f"(продажи {window}{qty_label(recent)}, остаток {qty_label(p.stock_qty)})."
        ),
        "details": {
            "sales": str(p.sales),
            "recent_sales": str(recent),
            "stock_qty": str(p.stock_qty),
            "suggest_qty": str(qty),
            "wear_type": p.wear_type,
            "lts": p.lts,
            "metal_color": p.metal_color,
            "bundle": bundle,
        },
    }


def successful_pattern_recommendations(patterns: list[PatternHit], top_n: int = RESTOCK_PER_CLIENT) -> list[dict]:
    ranked = [hit for hit in patterns if needs_restock(hit)]
    ranked.sort(key=lambda hit: (-score_pattern(hit), -float(pattern_velocity(hit))))
    used: dict[str, int] = {}
    picked: list[PatternHit] = []
    for hit in ranked:
        taken = used.get(hit.counterparty, 0)
        if taken >= top_n:
            continue
        used[hit.counterparty] = taken + 1
        picked.append(hit)
    return [_pattern_payload(hit) for hit in picked]


def price_arbitrage_recommendations(alerts: list[PriceArbitrageAlert]) -> list[dict]:
    out = []
    for a in alerts:
        if not has_bundle_attrs(a.wear_type, None, None):
            continue
        if a.sample_count < MIN_PRICE_SAMPLES:
            continue
        if not a.shipment_avg_price.is_finite() or not a.client_avg_price.is_finite():
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
                    f"Цена следующих отгрузок: не выше {money_label(a.client_avg_price)} тенге."
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
        best = max(hits, key=pattern_velocity)
        if not has_bundle_attrs(best.wear_type, best.lts, best.metal_color):
            continue
        if pattern_velocity(best) < MIN_PATTERN_SALES:
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
                "score": score_mix(worst.months_without_sales, worst.stock_qty, pattern_velocity(best)),
                "counterparty": counterparty,
                "article": worst.article,
                "message": (
                    f"Верните {qty_label(worst.stock_qty)} шт. {worst.article} "
                    f"({bundle_label(worst.wear_type, worst.lts, worst.metal_color)}, "
                    f"{worst.months_without_sales} мес. без продаж) и довезите "
                    f"«{bundle_label(best.wear_type, best.lts, best.metal_color)}» "
                    f"(продажи {qty_label(pattern_velocity(best))} шт.)."
                ),
                "details": {
                    "strong_bundle": bundle_label(best.wear_type, best.lts, best.metal_color),
                    "strong_sales": str(pattern_velocity(best)),
                    "weak_article": worst.article,
                    "weak_bundle": bundle_label(worst.wear_type, worst.lts, worst.metal_color),
                    "weak_stock": str(worst.stock_qty),
                    "suggest_qty": str(worst.stock_qty),
                    "months_without_sales": worst.months_without_sales,
                },
            }
        )
    return result


def score_transfer(months: int, qty: Decimal, recipient_score: int) -> int:
    return clamp_score(55 + months * 3 + min(20.0, float(qty)) + recipient_score * 0.15)


def transfer_recommendations(
    patterns: list[PatternHit],
    stocks: list[IlliquidCandidate],
    *,
    dwell_months: int = 6,
    per_donor: int = 1,
) -> list[dict]:
    recipients = [hit for hit in patterns if needs_restock(hit)]
    if not recipients:
        return []
    by_bundle: dict[tuple[str, str, str], list[PatternHit]] = {}
    for hit in recipients:
        by_bundle.setdefault(bundle_key(hit.wear_type, hit.lts, hit.metal_color), []).append(hit)
    for hits in by_bundle.values():
        hits.sort(key=lambda row: -score_pattern(row))

    donors = [
        item
        for item in stocks
        if item.stock_qty >= MIN_RETURN_QTY
        and item.months_without_sales > dwell_months
        and has_bundle_attrs(item.wear_type, item.lts, item.metal_color)
        and not is_exit_lts(item.lts)
    ]
    donors.sort(key=lambda item: (-item.months_without_sales, -float(item.stock_qty)))

    used_articles: set[tuple[str, str]] = set()
    used_need: set[tuple[str, tuple[str, str, str]]] = set()
    donor_count: dict[str, int] = {}
    result: list[dict] = []
    for donor in donors:
        key = bundle_key(donor.wear_type, donor.lts, donor.metal_color)
        if (donor.counterparty, donor.article) in used_articles:
            continue
        if donor_count.get(donor.counterparty, 0) >= per_donor:
            continue
        dests = [
            hit
            for hit in by_bundle.get(key, [])
            if hit.counterparty != donor.counterparty and (hit.counterparty, key) not in used_need
        ]
        if not dests:
            continue
        dest = dests[0]
        qty = min(donor.stock_qty, suggested_restock_qty(dest))
        if qty < 1:
            continue
        bundle = bundle_label(donor.wear_type, donor.lts, donor.metal_color)
        result.append(
            {
                "type": "transfer",
                "severity": "high" if donor.months_without_sales >= 8 else "medium",
                "action": "transfer",
                "title": f"Переложите {qty_label(qty)} шт. {donor.article} → {dest.counterparty}",
                "score": score_transfer(donor.months_without_sales, qty, score_pattern(dest)),
                "counterparty": donor.counterparty,
                "article": donor.article,
                "message": (
                    f"У {donor.counterparty} {donor.article} лежит {donor.months_without_sales} мес. "
                    f"У {dest.counterparty} связка «{bundle}» продаётся "
                    f"({qty_label(pattern_velocity(dest))} шт. за 3 мес.), "
                    f"остаток {qty_label(dest.stock_qty)}. Переложите {qty_label(qty)} шт."
                ),
                "details": {
                    "to_counterparty": dest.counterparty,
                    "bundle": bundle,
                    "suggest_qty": str(qty),
                    "stock_qty": str(donor.stock_qty),
                    "months_without_sales": donor.months_without_sales,
                    "wear_type": donor.wear_type,
                    "lts": donor.lts,
                    "metal_color": donor.metal_color,
                },
            }
        )
        used_articles.add((donor.counterparty, donor.article))
        used_need.add((dest.counterparty, key))
        donor_count[donor.counterparty] = donor_count.get(donor.counterparty, 0) + 1
    return result
