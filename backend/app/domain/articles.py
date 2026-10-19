"""Article / barcode normalization for 1C ↔ Excel matching."""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from numbers import Integral
from typing import Any, Iterable, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Nomenclature, NomenclatureBarcode

_FLOAT_INT = re.compile(r"^[+-]?\d+\.0+$")
_SCIENTIFIC = re.compile(r"^[+-]?\d+(\.\d+)?[eE][+-]?\d+$")


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


def _integral_text(value: Decimal) -> Optional[str]:
    if not value.is_finite():
        return None
    if value == value.to_integral_value():
        return str(int(value))
    return None


def normalize_article(value: Any) -> Optional[str]:
    """Trim Excel/1C SKU keys; coerce numeric barcodes like 3000008336986.0."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Decimal):
        integral = _integral_text(value)
        if integral is not None:
            return integral
        text = format(value, "f").rstrip("0").rstrip(".")
        return text or None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if abs(value - round(value)) < 1e-6:
            return str(int(round(value)))
        return str(value).strip() or None
    text = str(value).strip()
    if not text:
        return None
    compact = text.replace("\xa0", "").replace(" ", "")
    if compact.lower() in {"nan", "none", "null", "nat"}:
        return None
    if _FLOAT_INT.fullmatch(compact) or compact.isdigit():
        return compact.lstrip("+").split(".")[0]
    if _SCIENTIFIC.fullmatch(compact):
        try:
            integral = _integral_text(Decimal(compact))
            if integral is not None:
                return integral
        except InvalidOperation:
            pass
    return text


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


def barcode_lookup_keys(value: Any) -> set[str]:
    """Piece barcodes: keep padded series codes, expand only long EAN/passport numbers."""
    norm = normalize_article(value)
    if not norm:
        return set()
    keys = {norm}
    if norm.isdigit() and len(norm) >= 12:
        keys.add(str(int(norm)))
        keys.add(norm.lstrip("0") or "0")
    return keys


def lookup_keys_for_excel(value: Any) -> set[str]:
    """Article aliases, but do not collapse padded series codes like 0000002083 → 2083."""
    norm = normalize_article(value)
    if norm and norm.isdigit() and (len(norm) >= 12 or norm.startswith("0")):
        return barcode_lookup_keys(value)
    return article_lookup_keys(value) | barcode_lookup_keys(value)


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
    keys = lookup_keys_for_excel(article)
    if not keys:
        return None
    nom = db.scalar(
        select(Nomenclature)
        .where(
            or_(
                func.trim(Nomenclature.article).in_(keys),
                func.trim(Nomenclature.barcode).in_(keys),
            )
        )
        .limit(1)
    )
    if nom:
        return nom
    link = db.scalar(select(NomenclatureBarcode).where(NomenclatureBarcode.barcode.in_(keys)).limit(1))
    if not link:
        return None
    return db.scalar(
        select(Nomenclature).where(
            Nomenclature.source_id == link.source_id,
            Nomenclature.onec_ref == link.nomenclature_onec_ref,
        )
    )


def index_nomenclature(items: list[Nomenclature]) -> dict[str, Nomenclature]:
    index: dict[str, Nomenclature] = {}
    for nom in items:
        for raw in (nom.article, nom.barcode):
            for key in article_lookup_keys(raw):
                index.setdefault(key, nom)
    return index


def lookup_nomenclature(index: dict[str, Nomenclature], article: str) -> Optional[Nomenclature]:
    for key in lookup_keys_for_excel(article):
        found = index.get(key)
        if found:
            return found
    return None


def prefer_nomenclature_for_source(
    candidates: Iterable[Nomenclature],
    *,
    source_id: Optional[str] = None,
) -> Optional[Nomenclature]:
    """Prefer the twin from the same 1C base; otherwise first candidate."""
    rows = list(candidates)
    if not rows:
        return None
    if source_id:
        for nom in rows:
            if getattr(nom, "source_id", None) == source_id:
                return nom
    return rows[0]


def _nomenclatures_for_barcode_links(
    db: Session, links: list[NomenclatureBarcode]
) -> list[Nomenclature]:
    pairs = {(link.source_id, link.nomenclature_onec_ref) for link in links}
    if not pairs:
        return []
    clauses = [
        (Nomenclature.source_id == source_id) & (Nomenclature.onec_ref == onec_ref)
        for source_id, onec_ref in pairs
    ]
    return list(db.scalars(select(Nomenclature).where(or_(*clauses))).all())


def list_nomenclatures_for_articles(db: Session, articles: Iterable[str]) -> list[Nomenclature]:
    """All catalog rows matching articles or series barcodes (both bases)."""
    keys: set[str] = set()
    for article in articles:
        keys |= lookup_keys_for_excel(article)
    if not keys:
        return []
    by_id: dict[Any, Nomenclature] = {}
    for nom in db.scalars(
        select(Nomenclature).where(
            or_(
                func.trim(Nomenclature.article).in_(keys),
                func.trim(Nomenclature.barcode).in_(keys),
            )
        )
    ).all():
        by_id[nom.id] = nom
    links = list(db.scalars(select(NomenclatureBarcode).where(NomenclatureBarcode.barcode.in_(keys))).all())
    for nom in _nomenclatures_for_barcode_links(db, links):
        by_id[nom.id] = nom
    return list(by_id.values())


def index_nomenclature_for_articles(db: Session, articles: Iterable[str]) -> dict[str, Nomenclature]:
    keys: set[str] = set()
    for article in articles:
        keys |= lookup_keys_for_excel(article)
    if not keys:
        return {}
    noms = list_nomenclatures_for_articles(db, articles)
    index = index_nomenclature(noms)
    links = list(db.scalars(select(NomenclatureBarcode).where(NomenclatureBarcode.barcode.in_(keys))).all())
    by_ref = {(nom.source_id, nom.onec_ref): nom for nom in noms}
    for nom in _nomenclatures_for_barcode_links(db, links):
        by_ref[(nom.source_id, nom.onec_ref)] = nom
        for raw in (nom.article, nom.barcode):
            for key in article_lookup_keys(raw):
                index.setdefault(key, nom)
    for link in links:
        nom = by_ref.get((link.source_id, link.nomenclature_onec_ref))
        if not nom:
            continue
        for key in barcode_lookup_keys(link.barcode):
            index.setdefault(key, nom)
    return index


def unique_nomenclatures(index: dict[str, Nomenclature]) -> list[Nomenclature]:
    by_id: dict[Any, Nomenclature] = {}
    for nom in index.values():
        by_id[getattr(nom, "id", id(nom))] = nom
    return list(by_id.values())
