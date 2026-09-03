"""Trial sync: LTS history register → nomenclature.lts_date / lts."""
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

env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key.strip() == "DATABASE_URL":
            continue
        os.environ.setdefault(key.strip(), val.strip())

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.models import Nomenclature  # noqa: E402
from app.odata.client import ODataClient, ODataSource  # noqa: E402
from app.services.sync import sync_lts_history  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


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
        before_date = (
            db.scalar(select(func.count()).select_from(Nomenclature).where(Nomenclature.lts_date.isnot(None)))
            or 0
        )
        before_lts = (
            db.scalar(select(func.count()).select_from(Nomenclature).where(Nomenclature.lts.isnot(None))) or 0
        )
        print(f"BEFORE with lts_date={before_date} with lts={before_lts}")
        updated = sync_lts_history(db, source, full=True)
        print("SYNC updated=", updated)
        after_date = (
            db.scalar(select(func.count()).select_from(Nomenclature).where(Nomenclature.lts_date.isnot(None)))
            or 0
        )
        after_lts = (
            db.scalar(select(func.count()).select_from(Nomenclature).where(Nomenclature.lts.isnot(None))) or 0
        )
        total = db.scalar(select(func.count()).select_from(Nomenclature)) or 0
        print(f"AFTER nomenclature={total} with lts_date={after_date} with lts={after_lts}")
        for row in db.scalars(
            select(Nomenclature).where(Nomenclature.lts_date.isnot(None)).limit(8)
        ).all():
            print(" nom:", row.article, "|", row.name, "|", row.lts, "|", row.lts_date)
        print("DB file:", db_path)
    finally:
        db.close()


if __name__ == "__main__":
    main()
