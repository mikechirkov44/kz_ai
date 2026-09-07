from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import SYNC_SINCE_DEFAULTS, UserRole
from app.models import User
from app.security import hash_password
from app.services.llm_settings import ensure_llm_settings
from app.services.mail_settings import ensure_mail_settings
from app.services.odata_settings import ensure_odata_connections


def ensure_admin_user(db: Session) -> None:
    existing = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
    if existing:
        return
    db.add(
        User(
            email=settings.admin_email.lower(),
            password_hash=hash_password(settings.admin_password),
            role=UserRole.ADMIN.value,
            full_name="Administrator",
            active=True,
        )
    )
    db.commit()


def ensure_sync_since_column(engine: Engine) -> None:
    """Add sync_state.since_date on existing DBs. Seed defaults only when the column is new."""
    insp = inspect(engine)
    if "sync_state" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("sync_state")}
    if "since_date" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE sync_state ADD COLUMN since_date DATE"))
        for entity, since in SYNC_SINCE_DEFAULTS.items():
            conn.execute(
                text("UPDATE sync_state SET since_date = :d WHERE entity = :e"),
                {"d": since.isoformat(), "e": entity},
            )


def ensure_production_doc_number_column(engine: Engine) -> None:
    insp = inspect(engine)
    if "production_receipt" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("production_receipt")}
    if "doc_number" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE production_receipt ADD COLUMN doc_number VARCHAR(64)"))


def ensure_sync_schedule_time_columns(engine: Engine) -> None:
    insp = inspect(engine)
    if "sync_schedule" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("sync_schedule")}
    statements: list[str] = []
    if "mode" not in cols:
        statements.append("ALTER TABLE sync_schedule ADD COLUMN mode VARCHAR(16) DEFAULT 'interval'")
    if "run_at" not in cols:
        statements.append("ALTER TABLE sync_schedule ADD COLUMN run_at VARCHAR(5)")
    if not statements:
        return
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))


def ensure_odata_settings(db: Session) -> None:
    from app.services.sync import ensure_sync_state_rows

    ensure_odata_connections(db)
    ensure_llm_settings(db)
    ensure_mail_settings(db)
    from app.services.sync_schedule import ensure_sync_schedule

    ensure_sync_schedule(db)
    ensure_sync_state_rows(db)
