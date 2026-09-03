from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Optional
from uuid import UUID

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import UploadStatus, UploadType
from app.domain.excel_validation import validate_upload_dataframe
from app.models import ClientSale, ClientStock, Counterparty, Nomenclature, PromoMotivation, UploadLog
from app.schemas import UploadErrorItem, UploadResponse
from app.services.reports import resolve_sale_price


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def process_excel_upload(
    db: Session,
    *,
    user_id: Optional[UUID],
    file: UploadFile,
    upload_type: str,
    period_year: Optional[int] = None,
    period_month: Optional[int] = None,
    stock_date: Optional[date] = None,
) -> UploadResponse:
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"Файл больше {settings.max_upload_mb} МБ")

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    digest = _file_hash(content)
    dest = Path(settings.upload_dir) / f"{digest}_{file.filename}"
    dest.write_bytes(content)

    df = pd.read_excel(dest)
    if len(df) > settings.max_upload_rows:
        raise ValueError(f"Больше {settings.max_upload_rows} строк")

    records = df.where(pd.notnull(df), None).to_dict(orient="records")

    counterparties = db.scalars(
        select(Counterparty).where(Counterparty.is_folder.is_(False))
    ).all()
    known_cp = {c.name: c.id for c in counterparties}
    shops_map = {c.name: set(c.shops or []) for c in counterparties}

    noms = db.scalars(select(Nomenclature)).all()
    known_articles: set[str] = set()
    for n in noms:
        if n.article:
            known_articles.add(n.article)
        if n.barcode:
            known_articles.add(n.barcode)

    # If catalogs empty (pre-sync), validate structure only and accept rows
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
        )
        # drop "not found" style noise when bootstrapping without sync
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
        )

    upload = UploadLog(
        user_id=user_id,
        file_name=file.filename or "upload.xlsx",
        file_hash=digest,
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
                )
                db.add(cp)
                db.flush()
                known_cp[cp.name] = cp.id
                cp_id = cp.id

            if upload_type in {UploadType.SALES.value, UploadType.BOTH.value, "sales", "both"}:
                if period_year is None or period_month is None:
                    raise ValueError("Для продаж нужны period_year и period_month")
                price = resolve_sale_price(db, cp_id, row.article, row.price)
                db.add(
                    ClientSale(
                        upload_id=upload.id,
                        head_counterparty_id=cp_id,
                        article=row.article,
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
                        article=row.article,
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
                        article=row.article,
                        shop=row.shop,
                        quantity=row.quantity,
                        stock_date=stock_date,
                    )
                )
                processed += 1

    upload.processed_rows = processed
    upload.status = (
        UploadStatus.SUCCESS.value
        if not result.errors
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
