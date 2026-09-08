"""Article / barcode normalization for 1C ↔ Excel matching."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Nomenclature


def normalize_article(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def article_lookup_keys(value: Any) -> set[str]:
    """Excel often turns 000001797 into 1797 — accept both."""
    norm = normalize_article(value)
    if not norm:
        return set()
    keys = {norm}
    if norm.isdigit():
        keys.add(str(int(norm)))
        keys.add(norm.lstrip("0") or "0")
    return keys


def build_known_articles(nomenclatures: list[Nomenclature]) -> set[str]:
    known: set[str] = set()
    for nom in nomenclatures:
        for raw in (nom.article, nom.barcode):
            known |= article_lookup_keys(raw)
    return known


def find_nomenclature_by_article(db: Session, article: str) -> Optional[Nomenclature]:
    keys = article_lookup_keys(article)
    if not keys:
        return None
    return db.scalar(
        select(Nomenclature)
        .where(
            or_(
                func.trim(Nomenclature.article).in_(keys),
                func.trim(Nomenclature.barcode).in_(keys),
            )
        )
        .limit(1)
    )


def index_nomenclature(items: list[Nomenclature]) -> dict[str, Nomenclature]:
    index: dict[str, Nomenclature] = {}
    for nom in items:
        for raw in (nom.article, nom.barcode):
            for key in article_lookup_keys(raw):
                index.setdefault(key, nom)
    return index


def lookup_nomenclature(index: dict[str, Nomenclature], article: str) -> Optional[Nomenclature]:
    for key in article_lookup_keys(article):
        found = index.get(key)
        if found:
            return found
    return None


def index_nomenclature_for_articles(db: Session, articles: Iterable[str]) -> dict[str, Nomenclature]:
    keys: set[str] = set()
    for article in articles:
        keys |= article_lookup_keys(article)
    if not keys:
        return {}
    rows = list(
        db.scalars(
            select(Nomenclature).where(
                or_(
                    func.trim(Nomenclature.article).in_(keys),
                    func.trim(Nomenclature.barcode).in_(keys),
                )
            )
        ).all()
    )
    return index_nomenclature(rows)


def unique_nomenclatures(index: dict[str, Nomenclature]) -> list[Nomenclature]:
    by_id: dict[Any, Nomenclature] = {}
    for nom in index.values():
        by_id[getattr(nom, "id", id(nom))] = nom
    return list(by_id.values())
