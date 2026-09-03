"""Smoke health + login + fact-shipments against running API."""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

API = os.getenv("API_URL", "http://localhost:8000")
EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.models import Realization  # noqa: E402

PG = os.getenv("POSTGRES_URL", "postgresql+psycopg://kz_ai:kz_ai@postgres:5432/kz_ai")


def main() -> None:
    health = httpx.get(f"{API}/api/v1/health", timeout=30.0, verify=False)
    print("HEALTH", health.status_code, health.text[:400])

    login = httpx.post(
        f"{API}/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30.0,
    )
    print("LOGIN", login.status_code)
    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    cps = httpx.get(f"{API}/api/v1/counterparties", headers=headers, timeout=30.0)
    print("COUNTERPARTIES", cps.status_code, "count=", len(cps.json()) if cps.status_code == 200 else cps.text[:200])

    engine = create_engine(PG)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        start, end = date(2023, 1, 1), date(2023, 3, 31)
        top = db.execute(
            select(Realization.counterparty_id, func.count())
            .where(
                Realization.counterparty_id.isnot(None),
                Realization.doc_date >= start,
                Realization.doc_date <= end,
            )
            .group_by(Realization.counterparty_id)
            .order_by(func.count().desc())
            .limit(1)
        ).first()
    finally:
        db.close()

    if not top:
        print("No Q1-2023 realizations with linked counterparty")
        return
    cp_id, lines = top
    print(f"Q1 CP {cp_id} lines={lines}")
    fact = httpx.get(
        f"{API}/api/v1/reports/fact-shipments",
        params={"counterparty_id": str(cp_id), "year": 2023, "quarter": 1},
        headers=headers,
        timeout=60.0,
    )
    print("FACT", fact.status_code, fact.text[:500])

    turn = httpx.get(
        f"{API}/api/v1/reports/turnover",
        params={"view": "main", "year": 2023, "month": 1},
        headers=headers,
        timeout=30.0,
    )
    print("TURNOVER", turn.status_code, turn.text[:300])

    rec = httpx.get(f"{API}/api/v1/reports/recommendations", headers=headers, timeout=30.0)
    print("RECS", rec.status_code, rec.text[:300])


if __name__ == "__main__":
    main()
