"""Trial sync: nomenclature + counterparties from test3_asil into local SQLite."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Force local sqlite for trial (Docker may be unavailable)
db_path = ROOT / "data" / "trial_sync.db"
db_path.parent.mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"
os.environ.setdefault("ODATA_ASIL_URL", "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/")
# credentials: ODATA_ASIL_USER / ODATA_ASIL_PASSWORD or local 1c.txt
from _creds import load_1c_creds  # noqa: E402

_user, _password = load_1c_creds()
os.environ.setdefault("ODATA_ASIL_USER", _user)
os.environ.setdefault("ODATA_ASIL_PASSWORD", _password)
os.environ.setdefault("ODATA_ASIL_VERIFY_SSL", "false")

# Load .env overrides if present (except DATABASE_URL we force)
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
from app.models import Counterparty, Nomenclature  # noqa: E402
from app.odata.client import ODataClient, ODataSource  # noqa: E402
from app.services.sync import sync_catalogs_only  # noqa: E402

# SQLite needs check_same_thread
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
        # Patch sync to use our session's engine-bound session — sync uses Session from caller
        result = sync_catalogs_only(db, source, max_pages=15)
        print("SYNC RESULT:", result)
        nom_count = db.scalar(select(func.count()).select_from(Nomenclature)) or 0
        cp_count = db.scalar(select(func.count()).select_from(Counterparty)) or 0
        with_article = (
            db.scalar(select(func.count()).select_from(Nomenclature).where(Nomenclature.article.isnot(None))) or 0
        )
        print(f"DB nomenclature={nom_count} with_article={with_article}")
        print(f"DB counterparty={cp_count}")
        for s in db.scalars(select(Nomenclature).where(Nomenclature.article.isnot(None)).limit(5)).all():
            print(" nom:", s.article, "|", s.name, "|", s.lts, "|", s.direction, "|", s.wear_type)
        for c in db.scalars(select(Counterparty).where(Counterparty.is_folder.is_(False)).limit(5)).all():
            print(" cp:", c.name, "|", c.work_type, "|", c.shops)
        print("DB file:", db_path)
    finally:
        db.close()


if __name__ == "__main__":
    main()
