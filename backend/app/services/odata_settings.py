"""Resolve OData connections from DB (admin settings) with .env fallback."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import SOURCE_ASIL, SOURCE_MIAMOR
from app.models import ODataConnection
from app.odata.client import ODataSource
from app.security import decrypt_secret, encrypt_secret

KNOWN_SOURCES: tuple[tuple[str, str], ...] = (
    (SOURCE_ASIL, "Asil (test3_asil)"),
    (SOURCE_MIAMOR, "Mi Amor (вторая база)"),
)


def _env_defaults(source_id: str) -> dict:
    if source_id == SOURCE_ASIL:
        return {
            "label": "Asil (test3_asil)",
            "base_url": settings.odata_asil_url,
            "username": settings.odata_asil_user,
            "password": settings.odata_asil_password,
            "verify_ssl": settings.odata_asil_verify_ssl,
            "enabled": bool(settings.odata_asil_url),
        }
    return {
        "label": "Mi Amor (вторая база)",
        "base_url": settings.odata_miamor_url,
        "username": settings.odata_miamor_user,
        "password": settings.odata_miamor_password,
        "verify_ssl": settings.odata_miamor_verify_ssl,
        # Second base stays off until explicitly enabled in admin at the end
        "enabled": False,
    }


def ensure_odata_connections(db: Session) -> None:
    """Seed connection rows from .env if missing (miamor disabled by default)."""
    for source_id, label in KNOWN_SOURCES:
        existing = db.scalar(select(ODataConnection).where(ODataConnection.source_id == source_id))
        if existing:
            continue
        defaults = _env_defaults(source_id)
        password = defaults["password"] or ""
        db.add(
            ODataConnection(
                source_id=source_id,
                label=defaults.get("label") or label,
                base_url=defaults["base_url"] or "",
                username=defaults["username"] or "",
                password_encrypted=encrypt_secret(password) if password else "",
                verify_ssl=bool(defaults["verify_ssl"]),
                enabled=bool(defaults["enabled"]),
            )
        )
    db.commit()


def _row_to_source(row: ODataConnection) -> ODataSource:
    password = decrypt_secret(row.password_encrypted) if row.password_encrypted else ""
    return ODataSource(
        source_id=row.source_id,
        base_url=(row.base_url or "").strip(),
        username=(row.username or "").strip(),
        password=password,
        verify_ssl=bool(row.verify_ssl),
    )


def _env_to_source(source_id: str) -> ODataSource:
    d = _env_defaults(source_id)
    return ODataSource(
        source_id=source_id,
        base_url=(d["base_url"] or "").strip(),
        username=(d["username"] or "").strip(),
        password=d["password"] or "",
        verify_ssl=bool(d["verify_ssl"]),
    )


def get_connection_row(db: Session, source_id: str) -> Optional[ODataConnection]:
    return db.scalar(select(ODataConnection).where(ODataConnection.source_id == source_id))


def source_from_row(row: ODataConnection) -> ODataSource:
    return _row_to_source(row)


def resolve_source(db: Session, source_id: str, *, include_disabled: bool = False) -> Optional[ODataSource]:
    ensure_odata_connections(db)
    row = get_connection_row(db, source_id)
    if row:
        if row.enabled or include_disabled:
            if row.base_url:
                return _row_to_source(row)
            return None
        return None
    if source_id == SOURCE_MIAMOR:
        return None
    env_src = _env_to_source(source_id)
    return env_src if env_src.base_url else None


def configured_sources(db: Session) -> list[ODataSource]:
    ensure_odata_connections(db)
    result: list[ODataSource] = []
    for source_id, _ in KNOWN_SOURCES:
        src = resolve_source(db, source_id)
        if src and src.base_url:
            result.append(src)
    return result


def connection_public_view(row: ODataConnection) -> dict:
    return {
        "source_id": row.source_id,
        "label": row.label,
        "base_url": row.base_url,
        "username": row.username,
        "password_set": bool(row.password_encrypted),
        "verify_ssl": row.verify_ssl,
        "enabled": row.enabled,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def upsert_connection(
    db: Session,
    *,
    source_id: str,
    base_url: str,
    username: str,
    password: Optional[str],
    verify_ssl: bool,
    enabled: bool,
    label: Optional[str] = None,
) -> ODataConnection:
    ensure_odata_connections(db)
    row = get_connection_row(db, source_id)
    if not row:
        row = ODataConnection(source_id=source_id)
        db.add(row)
    row.base_url = (base_url or "").strip()
    row.username = (username or "").strip()
    row.verify_ssl = verify_ssl
    row.enabled = enabled
    if label is not None:
        row.label = label
    if password is not None and password != "":
        row.password_encrypted = encrypt_secret(password)
    db.flush()
    return row
