"""Seed ClientSale/ClientStock + is_promo from realization lines (trial/UAT)."""
from __future__ import annotations

import argparse
import sys
from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

DEFAULT_DB = ROOT / "data" / "trial_sync.db"

from sqlalchemy import create_engine, delete, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.domain.articles import normalize_article  # noqa: E402
from app.domain.fact_shipments import quarter_bounds  # noqa: E402
from app.models import ClientSale, ClientStock, Counterparty, Nomenclature, Realization, UploadLog  # noqa: E402
from app.services.counterparty_utils import mark_counterparties_promo, resolve_head_counterparty_id  # noqa: E402

SEED_HASH_PREFIX = "seed_realizations"


def _seed_hash(year: int, quarter: int) -> str:
    return f"{SEED_HASH_PREFIX}_y{year}_q{quarter}"


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def seed_from_realizations(
    db,
    *,
    year: int,
    quarter: int,
    stock_multiplier: Decimal = Decimal("2"),
    min_lines: int = 5,
    limit_counterparties: int | None = None,
) -> dict:
    start, end = quarter_bounds(year, quarter)
    file_hash = _seed_hash(year, quarter)

    existing = db.scalar(select(UploadLog).where(UploadLog.file_hash == file_hash))
    if existing:
        db.execute(delete(ClientSale).where(ClientSale.upload_id == existing.id))
        db.execute(delete(ClientStock).where(ClientStock.upload_id == existing.id))
        db.delete(existing)
        db.flush()

    realizations = db.scalars(
        select(Realization).where(
            Realization.doc_date >= start,
            Realization.doc_date <= end,
            Realization.counterparty_id.isnot(None),
            Realization.nomenclature_id.isnot(None),
            Realization.quantity > 0,
        )
    ).all()
    if not realizations:
        return {"error": "no realizations in period", "year": year, "quarter": quarter}

    nom_cache: dict[UUID, Nomenclature | None] = {}
    article_by_nom: dict[UUID, str] = {}

    def article_for(nom_id: UUID) -> str | None:
        if nom_id not in article_by_nom:
            nom = nom_cache.get(nom_id)
            if nom is None:
                nom = db.get(Nomenclature, nom_id)
                nom_cache[nom_id] = nom
            raw = (nom.article if nom else None) or (nom.barcode if nom else None)
            article_by_nom[nom_id] = normalize_article(raw) or ""
        return article_by_nom[nom_id] or None

    # sales: (head_cp, year, month, article) -> qty, amount
    sales_agg: dict[tuple[UUID, int, int, str], dict[str, Decimal]] = defaultdict(
        lambda: {"qty": Decimal(0), "amount": Decimal(0)}
    )
    cp_line_count: dict[UUID, int] = defaultdict(int)

    for r in realizations:
        article = article_for(r.nomenclature_id)
        if not article:
            continue
        head_id = resolve_head_counterparty_id(db, r.counterparty_id)
        key = (head_id, r.doc_date.year, r.doc_date.month, article)
        sales_agg[key]["qty"] += Decimal(r.quantity)
        sales_agg[key]["amount"] += Decimal(r.amount or 0)
        cp_line_count[head_id] += 1

    eligible_heads = {cp_id for cp_id, n in cp_line_count.items() if n >= min_lines}
    if limit_counterparties:
        top = sorted(
            ((cp_id, cp_line_count[cp_id]) for cp_id in eligible_heads),
            key=lambda x: x[1],
            reverse=True,
        )[:limit_counterparties]
        eligible_heads = {cp_id for cp_id, _ in top}

    upload = UploadLog(
        file_name=f"seed_realizations_{year}_Q{quarter}.csv",
        file_hash=file_hash,
        upload_type="seed",
        status="success",
        processed_rows=0,
        period_year=year,
        period_month=start.month,
        stock_date=end,
    )
    db.add(upload)
    db.flush()

    sales_rows = 0
    stock_rows = 0
    for (head_id, y, m, article), vals in sales_agg.items():
        if head_id not in eligible_heads:
            continue
        qty = vals["qty"]
        price = (vals["amount"] / qty).quantize(Decimal("0.01")) if qty else Decimal(0)
        db.add(
            ClientSale(
                upload_id=upload.id,
                head_counterparty_id=head_id,
                article=article,
                quantity=qty,
                price=price,
                period_year=y,
                period_month=m,
            )
        )
        sales_rows += 1
        stock_qty = (qty * stock_multiplier).quantize(Decimal("0.0001"))
        if stock_qty <= 0:
            stock_qty = qty
        db.add(
            ClientStock(
                upload_id=upload.id,
                head_counterparty_id=head_id,
                article=article,
                quantity=stock_qty,
                stock_date=_month_end(y, m),
            )
        )
        stock_rows += 1

    mark_counterparties_promo(db, eligible_heads, is_promo=True)
    upload.processed_rows = sales_rows + stock_rows
    db.commit()

    promo_count = db.scalar(
        select(func.count())
        .select_from(Counterparty)
        .where(Counterparty.is_promo.is_(True), Counterparty.is_folder.is_(False))
    )
    return {
        "year": year,
        "quarter": quarter,
        "realizations": len(realizations),
        "promo_counterparties": len(eligible_heads),
        "client_sales": sales_rows,
        "client_stocks": stock_rows,
        "total_promo_in_db": promo_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed report tables from realizations")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--quarter", type=int, default=1, choices=[1, 2, 3, 4])
    parser.add_argument("--stock-multiplier", type=Decimal, default=Decimal("2"))
    parser.add_argument("--min-lines", type=int, default=5)
    parser.add_argument("--limit-cp", type=int, default=None, help="Top N counterparties by line count")
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy URL (default: data/trial_sync.db)",
    )
    args = parser.parse_args()

    url = args.database_url or f"sqlite+pysqlite:///{DEFAULT_DB.as_posix()}"
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        result = seed_from_realizations(
            db,
            year=args.year,
            quarter=args.quarter,
            stock_multiplier=args.stock_multiplier,
            min_lines=args.min_lines,
            limit_counterparties=args.limit_cp,
        )
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
