"""Article / barcode normalization for 1C ↔ Excel matching."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Nomenclature


def nomenclature_label(article: Any, name: Any = None) -> str:
    """One nomenclature title. Do not repeat the article when the name already has it."""
    art = str(article or "").strip()
    title = str(name or "").strip()
    if not title:
        return art
    if art and title.casefold().startswith(art.casefold()):
        return title
    return title


def normalize_counterparty_name(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def is_retail_buyer(name: Any) -> bool:
    return normalize_counterparty_name(name) == "розничный покупатель"


# Latin lookalikes often typed instead of Cyrillic jewelry article prefixes.
_ARTICLE_LATIN_TO_CYR = str.maketrans(
    {
        "A": "А",
        "a": "а",
        "B": "В",
        "E": "Е",
        "e": "е",
        "K": "К",
        "k": "к",
        "M": "М",
        "m": "м",
        "H": "Н",
        "O": "О",
        "o": "о",
        "P": "Р",
        "p": "р",
        "C": "С",
        "c": "с",
        "T": "Т",
        "t": "т",
        "X": "Х",
        "x": "х",
    }
)
_ARTICLE_CYR_TO_LATIN = str.maketrans(
    {
        "А": "A",
        "а": "a",
        "В": "B",
        "Е": "E",
        "е": "e",
        "К": "K",
        "к": "k",
        "М": "M",
        "м": "m",
        "Н": "H",
        "О": "O",
        "о": "o",
        "Р": "P",
        "р": "p",
        "С": "C",
        "с": "c",
        "Т": "T",
        "т": "t",
        "Х": "X",
        "х": "x",
    }
)


def normalize_article(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def article_script_variants(value: Any) -> set[str]:
    """Same article typed with Latin or Cyrillic lookalike letters."""
    norm = normalize_article(value)
    if not norm:
        return set()
    variants = {norm}
    cyr = norm.translate(_ARTICLE_LATIN_TO_CYR)
    lat = norm.translate(_ARTICLE_CYR_TO_LATIN)
    if cyr:
        variants.add(cyr)
    if lat:
        variants.add(lat)
    return variants


def article_lookup_keys(value: Any) -> set[str]:
    """Excel often turns 000001797 into 1797 — accept both."""
    keys: set[str] = set()
    for norm in article_script_variants(value):
        keys.add(norm)
        if norm.isdigit():
            keys.add(str(int(norm)))
            keys.add(norm.lstrip("0") or "0")
    return keys


def article_search_patterns(value: Any) -> list[str]:
    """ILIKE patterns for nomenclature search (Latin/Cyrillic lookalikes)."""
    text = (normalize_article(value) or "").strip()
    if not text:
        return []
    return [f"%{variant}%" for variant in sorted(article_script_variants(text))]


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
