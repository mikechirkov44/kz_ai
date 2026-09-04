"""Run domain reports against trial SQLite (or --database-url)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

DEFAULT_DB = ROOT / "data" / "trial_sync.db"

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.models import ClientSale, Counterparty, Nomenclature, Realization  # noqa: E402
from app.services.ai import generate_recommendations  # noqa: E402
from app.services.reports import (  # noqa: E402
    build_motivation_report,
    build_quarterly_plans_report,
    build_turnover_report,
    compute_fact_shipments,
)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    url = args.database_url or f"sqlite+pysqlite:///{DEFAULT_DB.as_posix()}"

    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        nom = db.scalar(select(func.count()).select_from(Nomenclature)) or 0
        cp = db.scalar(select(func.count()).select_from(Counterparty)) or 0
        real = db.scalar(select(func.count()).select_from(Realization)) or 0
        print(f"DB {url.split('://', 1)[0]} nomenclature={nom} counterparties={cp} realizations={real}")

        # Pick a counterparty with the most realization lines in 2023 Q1
        top = db.execute(
            select(Realization.counterparty_id, func.count())
            .where(Realization.counterparty_id.isnot(None))
            .group_by(Realization.counterparty_id)
            .order_by(func.count().desc())
            .limit(1)
        ).first()
        if not top:
            print("No linked realizations — cannot run fact shipments")
            return
        cp_id, lines = top
        counterparty = db.get(Counterparty, cp_id)
        print(f"Top CP {counterparty.name if counterparty else cp_id} lines={lines}")

        fact = compute_fact_shipments(db, counterparty_id=cp_id, year=2023, quarter=1)
        print(
            "FACT Q1-2023",
            f"fact={fact.fact_amount}",
            f"excluded_illiquid={fact.excluded_illiquid_amount}",
        )

        mot = build_motivation_report(db, counterparty_id=cp_id, year=2023, month=1)
        print("MOTIVATION 2023-01 items=", len(mot.items), "total=", mot.total_bonus)

        promo_sale = db.execute(
            select(ClientSale.head_counterparty_id, func.count())
            .join(Counterparty, Counterparty.id == ClientSale.head_counterparty_id)
            .where(
                Counterparty.is_promo.is_(True),
                ClientSale.period_year == 2023,
                ClientSale.period_month == 1,
            )
            .group_by(ClientSale.head_counterparty_id)
            .order_by(func.count().desc())
            .limit(1)
        ).first()
        if promo_sale:
            promo_id, sale_lines = promo_sale
            promo_cp = db.get(Counterparty, promo_id)
            mot_promo = build_motivation_report(db, counterparty_id=promo_id, year=2023, month=1)
            print(
                f"MOTIVATION promo CP {promo_cp.name if promo_cp else promo_id}",
                f"items={len(mot_promo.items)}",
                f"total={mot_promo.total_bonus}",
            )

        turn = build_turnover_report(db, view="main", year=2023, month=1)
        print("TURNOVER main rows=", len(turn.data), "(needs promo counterparties + Excel sales/stocks)")

        q = build_quarterly_plans_report(db, year=2023, quarter=1)
        print("QUARTERLY clients=", len(q.clients))

        rec = generate_recommendations(db, counterparty_id=None)
        print("AI recs=", len(rec.items))
    finally:
        db.close()


if __name__ == "__main__":
    main()
