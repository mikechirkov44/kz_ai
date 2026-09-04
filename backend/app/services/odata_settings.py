"""Resolve OData connections from DB (admin settings) with .env fallback."""

from __future__ import annotations

import re
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import SOURCE_ASIL, SOURCE_MIAMOR
from app.models import ODataConnection
from app.odata.client import ODataSource
from app.security import decrypt_secret, encrypt_secret

SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

# Env-backed seed slots. Labels are generic; admin can rename in UI.
SEEDED_SOURCES: tuple[tuple[str, str], ...] = (
    (SOURCE_ASIL, "Асыл"),
    (SOURCE_MIAMOR, "МиАмор"),
)


def is_valid_source_id(source_id: str) -> bool:
    return bool(SOURCE_ID_RE.fullmatch(source_id or ""))


def next_source_id(existing: Iterable[str]) -> str:
    taken = set(existing)
    n = 1
    while f"base_{n}" in taken:
        n += 1
    return f"base_{n}"


def _env_defaults(source_id: str) -> dict:
    if source_id == SOURCE_ASIL:
        return {
            "label": "Асыл",
            "base_url": settings.odata_asil_url,
            "username": settings.odata_asil_user,
            "password": settings.odata_asil_password,
            "verify_ssl": settings.odata_asil_verify_ssl,
            "enabled": bool(settings.odata_asil_url),
        }
    return {
        "label": "МиАмор",
        "base_url": settings.odata_miamor_url,
        "username": settings.odata_miamor_user,
        "password": settings.odata_miamor_password,
        "verify_ssl": settings.odata_miamor_verify_ssl,
        "enabled": bool(settings.odata_miamor_url),
    }


def ensure_odata_connections(db: Session) -> None:
    """Seed connection rows from .env if missing; rename leftover default labels."""
    legacy_labels = {
        SOURCE_ASIL: {"Asil (test3_asil)", "База 1"},
        SOURCE_MIAMOR: {"Mi Amor (вторая база)", "База 2"},
    }
    for source_id, label in SEEDED_SOURCES:
        existing = db.scalar(select(ODataConnection).where(ODataConnection.source_id == source_id))
        defaults = _env_defaults(source_id)
        if existing:
            if existing.label in legacy_labels.get(source_id, set()):
                existing.label = label
            # Fill empty connection from .env (e.g. second base added later).
            if not (existing.base_url or "").strip() and defaults.get("base_url"):
                existing.base_url = defaults["base_url"]
                existing.username = defaults.get("username") or existing.username
                password = defaults.get("password") or ""
                if password:
                    existing.password_encrypted = encrypt_secret(password)
                existing.verify_ssl = bool(defaults.get("verify_ssl"))
                existing.enabled = True
                if not (existing.label or "").strip() or existing.label in legacy_labels.get(source_id, set()):
                    existing.label = defaults.get("label") or label
            continue
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


def list_connection_rows(db: Session) -> list[ODataConnection]:
    ensure_odata_connections(db)
    return list(
        db.scalars(
            select(ODataConnection).order_by(ODataConnection.created_at, ODataConnection.source_id)
        ).all()
    )


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
    env_src = _env_to_source(source_id)
    return env_src if env_src.base_url else None


def configured_sources(db: Session) -> list[ODataSource]:
    result: list[ODataSource] = []
    for row in list_connection_rows(db):
        if row.enabled and row.base_url:
            result.append(_row_to_source(row))
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


def source_public_view(row: ODataConnection) -> dict:
    return {
        "source_id": row.source_id,
        "label": row.label or row.source_id,
        "enabled": bool(row.enabled),
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
        row.label = label.strip()
    if password is not None and password != "":
        row.password_encrypted = encrypt_secret(password)
    db.flush()
    return row


def create_connection(
    db: Session,
    *,
    label: str,
    base_url: str = "",
    username: str = "",
    password: Optional[str] = None,
    verify_ssl: bool = False,
    enabled: bool = False,
) -> ODataConnection:
    ensure_odata_connections(db)
    taken = {row.source_id for row in list_connection_rows(db)}
    source_id = next_source_id(taken)
    name = (label or "").strip() or f"База {source_id}"
    row = ODataConnection(
        source_id=source_id,
        label=name,
        base_url=(base_url or "").strip(),
        username=(username or "").strip(),
        password_encrypted=encrypt_secret(password) if password else "",
        verify_ssl=verify_ssl,
        enabled=enabled,
    )
    db.add(row)
    db.flush()
    return row
