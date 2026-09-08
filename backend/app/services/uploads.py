from __future__ import annotations

import hashlib
import io
from datetime import date
from pathlib import Path
from typing import Optional
from uuid import UUID

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import UploadStatus, UploadType, UserRole
from app.domain.articles import (
    article_lookup_keys,
    build_known_articles,
    index_nomenclature_for_articles,
    normalize_article,
    unique_nomenclatures,
)
from app.domain.excel_validation import (
    RowError,
    articles_from_records,
    normalize_counterparty_name,
    validate_upload_dataframe,
)
from app.domain.manual_upload import MANUAL_FILE_NAME, records_from_manual_rows, require_manual_period
from app.domain.quarterly_plan_upload import parse_quarterly_plan_records
from app.models import (
    ClientSale,
    ClientStock,
    Counterparty,
    PromoMotivation,
    QuarterlyPlan,
    UploadLog,
    User,
)
from app.schemas import ManualUploadRequest, UploadErrorItem, UploadPreviewResponse, UploadResponse
from app.services.counterparty_utils import mark_counterparties_promo
from app.services.reports import resolve_sale_price


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def stored_upload_path(file_hash: str, file_name: str) -> Path:
    return Path(settings.upload_dir) / f"{file_hash}_{file_name}"


def _validate_records(
    db: Session,
    records: list[dict],
    *,
    start_row: int = 2,
    empty_message: str = "Файл пуст",
) -> tuple:
    counterparties = db.scalars(select(Counterparty).where(Counterparty.is_folder.is_(False))).all()
    known_cp = {normalize_counterparty_name(c.name): c.id for c in counterparties if c.name}
    shops_map = {normalize_counterparty_name(c.name): set(c.shops or []) for c in counterparties if c.name}

    noms = unique_nomenclatures(index_nomenclature_for_articles(db, articles_from_records(records)))
    known_articles = build_known_articles(noms)
    alias_to_article: dict[str, str] = {}
    for nom in noms:
        canonical = normalize_article(nom.article) or normalize_article(nom.barcode)
        if not canonical:
            continue
        for key in article_lookup_keys(nom.article) | article_lookup_keys(nom.barcode):
            alias_to_article[key] = canonical

    extra = {"start_row": start_row, "empty_message": empty_message}
    if not known_cp:
        structural = validate_upload_dataframe(
            records,
            known_counterparties={
                str(list(r.values())[0]).strip(): "tmp"
                for r in records
                if r and list(r.values())
            },
            known_articles={
                str(list(r.values())[1]).strip()
                for r in records
                if r and len(list(r.values())) > 1 and list(r.values())[1]
            },
            counterparty_shops={},
            require_price=False,
            **extra,
        )
        structural.errors = [
            e
            for e in structural.errors
            if "не существует" not in e.message.lower() and "не найден" not in e.message.lower()
        ]
        result = structural
    else:
        result = validate_upload_dataframe(
            records,
            known_counterparties=known_cp,
            known_articles=known_articles,
            counterparty_shops=shops_map,
            require_price=False,
            **extra,
        )
    return result, known_cp, alias_to_article


async def preview_excel_upload(
    db: Session,
    *,
    file: UploadFile,
) -> UploadPreviewResponse:
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"Файл больше {settings.max_upload_mb} МБ")

    df = pd.read_excel(io.BytesIO(content))
    if len(df) > settings.max_upload_rows:
        raise ValueError(f"Больше {settings.max_upload_rows} строк")

    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    result, _, _ = _validate_records(db, records)
    errors = [UploadErrorItem(**e.as_dict()) for e in result.errors]
    valid_rows = len(result.rows)
    sample = [
        {
            "row": r.row_number,
            "counterparty": r.head_counterparty_name,
            "article": r.article,
            "shop": r.shop,
            "quantity": float(r.quantity),
            "price": float(r.price) if r.price is not None else None,
        }
        for r in result.rows[:10]
    ]
    return UploadPreviewResponse(
        status=result.status,
        total_rows=len(records),
        valid_rows=valid_rows,
        error_count=len(errors),
        errors=errors[:100],
        sample_rows=sample,
    )


async def process_excel_upload(
    db: Session,
    *,
    user_id: Optional[UUID],
    file: UploadFile,
    upload_type: str,
    period_year: Optional[int] = None,
    period_month: Optional[int] = None,
    stock_date: Optional[date] = None,
    actor: Optional[User] = None,
) -> UploadResponse:
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"Файл больше {settings.max_upload_mb} МБ")

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    digest = _file_hash(content)
    dest = stored_upload_path(digest, file.filename or "upload.xlsx")
    dest.write_bytes(content)

    df = pd.read_excel(dest)
    if len(df) > settings.max_upload_rows:
        raise ValueError(f"Больше {settings.max_upload_rows} строк")

    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    result, known_cp, alias_to_article = _validate_records(db, records)
    return _persist_validated_upload(
        db,
        user_id=user_id,
        file_name=file.filename or "upload.xlsx",
        file_hash=digest,
        upload_type=upload_type,
        period_year=period_year,
        period_month=period_month,
        stock_date=stock_date,
        actor=actor,
        result=result,
        known_cp=known_cp,
        alias_to_article=alias_to_article,
    )


def process_manual_upload(
    db: Session,
    *,
    user_id: Optional[UUID],
    payload: ManualUploadRequest,
    actor: Optional[User] = None,
) -> UploadResponse:
    require_manual_period(
        payload.upload_type,
        period_year=payload.period_year,
        period_month=payload.period_month,
        stock_date=payload.stock_date,
    )
    records = records_from_manual_rows([row.model_dump() for row in payload.rows])
    if len(records) > settings.max_upload_rows:
        raise ValueError(f"Больше {settings.max_upload_rows} строк")
    result, known_cp, alias_to_article = _validate_records(
        db,
        records,
        start_row=1,
        empty_message="Нет строк для загрузки",
    )
    digest = _file_hash(payload.model_dump_json().encode())
    return _persist_validated_upload(
        db,
        user_id=user_id,
        file_name=MANUAL_FILE_NAME,
        file_hash=digest,
        upload_type=payload.upload_type,
        period_year=payload.period_year,
        period_month=payload.period_month,
        stock_date=payload.stock_date,
        actor=actor,
        result=result,
        known_cp=known_cp,
        alias_to_article=alias_to_article,
    )


def _persist_validated_upload(
    db: Session,
    *,
    user_id: Optional[UUID],
    file_name: str,
    file_hash: str,
    upload_type: str,
    period_year: Optional[int],
    period_month: Optional[int],
    stock_date: Optional[date],
    actor: Optional[User],
    result,
    known_cp: dict,
    alias_to_article: dict[str, str],
) -> UploadResponse:
    upload = UploadLog(
        user_id=user_id,
        file_name=file_name,
        file_hash=file_hash,
        upload_type=upload_type,
        status=result.status,
        processed_rows=0,
        errors=[e.as_dict() for e in result.errors],
        period_year=period_year,
        period_month=period_month,
        stock_date=stock_date,
    )
    db.add(upload)
    db.flush()

    processed = 0
    promo_counterparties: set[UUID] = set()
    extra_errors: list[dict] = []
    if result.rows and result.status in {UploadStatus.SUCCESS.value, UploadStatus.PARTIAL.value, "success", "partial"}:
        for row in result.rows:
            cp_id = known_cp.get(row.head_counterparty_name)
            if not cp_id and known_cp:
                continue
            if not cp_id:
                # create placeholder counterparty for demo without sync
                cp = Counterparty(
                    source_id="manual",
                    onec_ref=f"manual-{row.head_counterparty_name}",
                    name=row.head_counterparty_name,
                    is_promo=True,
                    shops=[row.shop] if row.shop else [],
                    manager_id=actor.id if actor and actor.role == UserRole.MANAGER.value else None,
                )
                db.add(cp)
                db.flush()
                known_cp[cp.name] = cp.id
                cp_id = cp.id

            if actor and actor.role == UserRole.MANAGER.value:
                owned = db.get(Counterparty, cp_id)
                if owned and owned.manager_id not in (None, actor.id):
                    extra_errors.append(
                        RowError(
                            row.row_number,
                            "head_counterparty",
                            f"Контрагент «{row.head_counterparty_name}» закреплён за другим менеджером",
                        ).as_dict()
                    )
                    continue
                if owned and owned.manager_id is None:
                    owned.manager_id = actor.id

            article = alias_to_article.get(normalize_article(row.article) or "", normalize_article(row.article) or row.article)
            promo_counterparties.add(cp_id)

            if upload_type in {UploadType.SALES.value, UploadType.BOTH.value, "sales", "both"}:
                if period_year is None or period_month is None:
                    raise ValueError("Для продаж нужны period_year и period_month")
                price = resolve_sale_price(db, cp_id, article, row.price)
                if price is None:
                    extra_errors.append(
                        RowError(
                            row.row_number,
                            "price",
                            "Нет реализаций 1С для расчёта цены продажи",
                        ).as_dict()
                    )
                else:
                    db.add(
                        ClientSale(
                            upload_id=upload.id,
                            head_counterparty_id=cp_id,
                            article=article,
                            shop=row.shop,
                            quantity=row.quantity,
                            price=price,
                            period_year=period_year,
                            period_month=period_month,
                        )
                    )
                    processed += 1

            if upload_type in {UploadType.STOCKS.value, UploadType.BOTH.value, "stocks", "both"}:
                if stock_date is None:
                    raise ValueError("Для остатков нужна stock_date")
                db.add(
                    ClientStock(
                        upload_id=upload.id,
                        head_counterparty_id=cp_id,
                        article=article,
                        shop=row.shop,
                        quantity=row.quantity,
                        stock_date=stock_date,
                    )
                )
                processed += 1

            if upload_type in {UploadType.PROMO_MOTIVATION.value, "promo_motivation"}:
                db.add(
                    PromoMotivation(
                        upload_id=upload.id,
                        counterparty_id=cp_id,
                        article=article,
                        shop=row.shop,
                        quantity=row.quantity,
                        stock_date=stock_date,
                    )
                )
                processed += 1

        if promo_counterparties:
            mark_counterparties_promo(db, promo_counterparties, is_promo=True)

    upload.processed_rows = processed
    if extra_errors:
        upload.errors = (upload.errors or []) + extra_errors
    upload.status = (
        UploadStatus.SUCCESS.value
        if not upload.errors
        else (UploadStatus.PARTIAL.value if processed else UploadStatus.ERROR.value)
    )
    db.commit()
    db.refresh(upload)

    return UploadResponse(
        upload_id=upload.id,
        status=upload.status,
        processed_rows=upload.processed_rows,
        errors=[UploadErrorItem(**e) for e in (upload.errors or [])],
    )


async def process_quarterly_plan_upload(
    db: Session,
    *,
    user_id: Optional[UUID],
    file: UploadFile,
    actor: Optional[User] = None,
) -> UploadResponse:
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"Файл больше {settings.max_upload_mb} МБ")

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    digest = _file_hash(content)
    dest = stored_upload_path(digest, file.filename or "quarterly_plans.xlsx")
    dest.write_bytes(content)

    df = pd.read_excel(dest)
    if len(df) > settings.max_upload_rows:
        raise ValueError(f"Больше {settings.max_upload_rows} строк")

    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    counterparties = db.scalars(select(Counterparty).where(Counterparty.is_folder.is_(False))).all()
    known_cp = {normalize_counterparty_name(c.name): c.id for c in counterparties if c.name}
    parsed = parse_quarterly_plan_records(records, known_counterparties=known_cp)

    extra_errors: list[dict] = []
    processed = 0
    for row in parsed.rows:
        cp_id = known_cp.get(row.head_counterparty_name)
        if not cp_id:
            continue
        if actor and actor.role == UserRole.MANAGER.value:
            owned = db.get(Counterparty, cp_id)
            if owned and owned.manager_id not in (None, actor.id):
                extra_errors.append(
                    RowError(
                        row.row_number,
                        "head_counterparty",
                        f"Контрагент «{row.head_counterparty_name}» закреплён за другим менеджером",
                    ).as_dict()
                )
                continue
        existing = db.scalar(
            select(QuarterlyPlan).where(
                QuarterlyPlan.year == row.year,
                QuarterlyPlan.quarter == row.quarter,
                QuarterlyPlan.counterparty_id == cp_id,
            )
        )
        if existing:
            existing.plan_value = row.plan_value
        else:
            db.add(
                QuarterlyPlan(
                    year=row.year,
                    quarter=row.quarter,
                    counterparty_id=cp_id,
                    plan_value=row.plan_value,
                    manager_id=actor.id if actor else user_id,
                )
            )
        processed += 1

    errors = [e.as_dict() for e in parsed.errors] + extra_errors
    status = (
        UploadStatus.SUCCESS.value
        if not errors
        else (UploadStatus.PARTIAL.value if processed else UploadStatus.ERROR.value)
    )
    upload = UploadLog(
        user_id=user_id,
        file_name=file.filename or "quarterly_plans.xlsx",
        file_hash=digest,
        upload_type=UploadType.QUARTERLY_PLANS.value,
        status=status,
        processed_rows=processed,
        errors=errors,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return UploadResponse(
        upload_id=upload.id,
        status=upload.status,
        processed_rows=upload.processed_rows,
        errors=[UploadErrorItem(**e) for e in (upload.errors or [])],
    )
