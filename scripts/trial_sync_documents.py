"""Trial sync: realizations + returns from test3_asil into local SQLite."""
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
from app.models import Realization, ReturnDoc  # noqa: E402
from app.odata.client import ODataClient, ODataSource  # noqa: E402
from app.services.sync import sync_documents_trial  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Realizations: ~4500 posted ≈ early 2023. Returns: fewer docs → start at 0.
MAX_PAGES = int(os.getenv("TRIAL_DOC_MAX_PAGES", "15"))
REAL_START_SKIP = int(os.getenv("TRIAL_REAL_START_SKIP", "4500"))
RET_START_SKIP = int(os.getenv("TRIAL_RET_START_SKIP", "0"))


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
        print(
            f"Trial docs: max_pages={MAX_PAGES} "
            f"real_skip={REAL_START_SKIP} ret_skip={RET_START_SKIP}"
        )
        result = sync_documents_trial(
            db,
            source,
            max_pages=MAX_PAGES,
            realization_start_skip=REAL_START_SKIP,
            return_start_skip=RET_START_SKIP,
        )
        print("SYNC RESULT:", result)
        real_count = db.scalar(select(func.count()).select_from(Realization)) or 0
        ret_count = db.scalar(select(func.count()).select_from(ReturnDoc)) or 0
        linked_nom = (
            db.scalar(
                select(func.count())
                .select_from(Realization)
                .where(Realization.nomenclature_id.isnot(None))
            )
            or 0
        )
        linked_cp = (
            db.scalar(
                select(func.count())
                .select_from(Realization)
                .where(Realization.counterparty_id.isnot(None))
            )
            or 0
        )
        print(f"DB realization={real_count} linked_nom={linked_nom} linked_cp={linked_cp}")
        print(f"DB return_doc={ret_count}")
        for row in db.scalars(select(Realization).limit(5)).all():
            print(
                " real:",
                row.doc_date,
                row.doc_number,
                "| qty",
                row.quantity,
                "| amt",
                row.amount,
                "| wh",
                row.warehouse,
                "| series",
                (row.series or "")[:8],
            )
        for row in db.scalars(select(ReturnDoc).limit(5)).all():
            print(
                " ret:",
                row.doc_date,
                row.doc_number,
                "| qty",
                row.quantity,
                "| amt",
                row.amount,
                "| wh",
                row.warehouse,
            )
        print("DB file:", db_path)
    finally:
        db.close()


if __name__ == "__main__":
    main()
