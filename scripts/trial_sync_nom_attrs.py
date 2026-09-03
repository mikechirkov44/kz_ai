"""Trial: re-sync nomenclature with catalog key lookups; print attribute fill rates."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

db_path = ROOT / "data" / "trial_sync.db"
db_path.parent.mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
os.environ.setdefault(
    "ODATA_ASIL_URL",
    "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/",
)

from _creds import load_1c_creds  # noqa: E402

_user, _password = load_1c_creds()
os.environ.setdefault("ODATA_ASIL_USER", _user)
os.environ.setdefault("ODATA_ASIL_PASSWORD", _password)
os.environ.setdefault("ODATA_ASIL_VERIFY_SSL", "false")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.models import Nomenclature  # noqa: E402
from app.odata.client import ODataClient, ODataSource  # noqa: E402
from app.services.sync import sync_lts_history, sync_nomenclature  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

MAX_PAGES = int(os.getenv("TRIAL_NOM_MAX_PAGES", "30"))


def _fill(db, field: str) -> int:
    col = getattr(Nomenclature, field)
    return db.scalar(select(func.count()).select_from(Nomenclature).where(col.isnot(None))) or 0


def main() -> None:
    Base.metadata.create_all(bind=engine)
    source = ODataSource(
        source_id="asil",
        base_url=os.environ["ODATA_ASIL_URL"],
        username=os.environ["ODATA_ASIL_USER"],
        password=os.environ["ODATA_ASIL_PASSWORD"],
        verify_ssl=False,
    )
    with ODataClient(source) as client:
        print("OData health:", client.health())

    db = SessionLocal()
    try:
        print("BEFORE", {f: _fill(db, f) for f in ("direction", "wear_type", "metal_color", "assay", "lts", "lts_date")})
        synced = sync_nomenclature(db, source, full=True, max_pages=MAX_PAGES)
        print("SYNC nomenclature=", synced)
        lts_upd = sync_lts_history(db, source, full=True)
        print("SYNC lts_history=", lts_upd)
        total = db.scalar(select(func.count()).select_from(Nomenclature)) or 0
        print("AFTER total=", total)
        print("AFTER", {f: _fill(db, f) for f in ("direction", "wear_type", "metal_color", "assay", "lts", "lts_date")})
        for row in db.scalars(
            select(Nomenclature).where(Nomenclature.direction.isnot(None)).limit(8)
        ).all():
            print(
                " nom:",
                (row.article or "")[:20],
                "|",
                row.direction,
                "|",
                row.wear_type,
                "|",
                row.metal_color,
                "|",
                row.assay,
                "|",
                row.lts,
                "|",
                row.lts_date,
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
