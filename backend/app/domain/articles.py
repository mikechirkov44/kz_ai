"""Article / barcode normalization for 1C ↔ Excel matching."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Nomenclature


def normalize_article(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_known_articles(nomenclatures: list[Nomenclature]) -> set[str]:
    known: set[str] = set()
    for nom in nomenclatures:
        for raw in (nom.article, nom.barcode):
            norm = normalize_article(raw)
            if norm:
                known.add(norm)
    return known


def find_nomenclature_by_article(db: Session, article: str) -> Optional[Nomenclature]:
    norm = normalize_article(article)
    if not norm:
        return None
    return db.scalar(
        select(Nomenclature)
        .where(
            or_(
                func.trim(Nomenclature.article) == norm,
                func.trim(Nomenclature.barcode) == norm,
            )
        )
        .limit(1)
    )
