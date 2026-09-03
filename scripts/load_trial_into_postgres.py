"""Copy trial SQLite catalogs/documents into Postgres (Docker)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

SRC_DB = Path(os.getenv("TRIAL_SQLITE", ROOT / "data" / "trial_sync.db"))
SRC_URL = f"sqlite+pysqlite:///{SRC_DB.as_posix()}"
DST_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+psycopg://kz_ai:kz_ai@postgres:5432/kz_ai",
)

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.models import Counterparty, Nomenclature, Realization, ReturnDoc  # noqa: E402

TABLES = (Nomenclature, Counterparty, Realization, ReturnDoc)


def _payload(model, row, *, drop: set[str] | None = None) -> dict:
    skip = drop or set()
    return {c.key: getattr(row, c.key) for c in model.__table__.columns if c.key not in skip}


def _copy(src, dst, model, batch: int = 500, *, drop: set[str] | None = None) -> int:
    rows = list(src.scalars(select(model)).all())
    copied = 0
    for i, row in enumerate(rows, start=1):
        dst.merge(model(**_payload(model, row, drop=drop)))
        copied += 1
        if i % batch == 0:
            dst.commit()
    dst.commit()
    return copied


def _restore_heads(src, dst) -> int:
    updated = 0
    for row in src.scalars(select(Counterparty)).all():
        if not row.head_counterparty_id:
            continue
        existing = dst.get(Counterparty, row.id)
        if existing and dst.get(Counterparty, row.head_counterparty_id):
            existing.head_counterparty_id = row.head_counterparty_id
            updated += 1
    dst.commit()
    return updated


def main() -> None:
    if not SRC_DB.exists():
        raise SystemExit(f"Missing {SRC_DB} — run trial sync scripts first")

    src_engine = create_engine(SRC_URL, connect_args={"check_same_thread": False})
    dst_engine = create_engine(DST_URL)
    Src = sessionmaker(bind=src_engine, autoflush=False, autocommit=False)
    Dst = sessionmaker(bind=dst_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=dst_engine)

    src = Src()
    dst = Dst()
    try:
        print("SRC", {m.__tablename__: src.scalar(select(func.count()).select_from(m)) for m in TABLES})
        n = _copy(src, dst, Counterparty, drop={"head_counterparty_id"})
        print(f"copied counterparty={n}")
        print(f"restored head links={_restore_heads(src, dst)}")
        n = _copy(src, dst, Nomenclature)
        print(f"copied nomenclature={n}")
        n = _copy(src, dst, Realization)
        print(f"copied realization={n}")
        n = _copy(src, dst, ReturnDoc)
        print(f"copied return_doc={n}")
        print("DST", {m.__tablename__: dst.scalar(select(func.count()).select_from(m)) for m in TABLES})
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
