"""Run domain reports against trial SQLite (or DATABASE_URL)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

db_path = ROOT / "data" / "trial_sync.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.models import Counterparty, Nomenclature, Realization  # noqa: E402
from app.services.ai import generate_recommendations  # noqa: E402
from app.services.reports import (  # noqa: E402
    build_motivation_report,
    build_quarterly_plans_report,
    build_turnover_report,
    compute_fact_shipments,
)

url = os.environ["DATABASE_URL"]
kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
engine = create_engine(url, **kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def main() -> None:
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
