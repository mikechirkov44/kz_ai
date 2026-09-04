from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session
import io
import pandas as pd

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user, require_roles, write_audit
from app.models import User
from app.schemas import UploadResponse
from app.services.uploads import process_excel_upload

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


def _xlsx_response(buf: io.BytesIO, filename: str) -> Response:
    data = buf.getvalue()
    if data[:2] != b"PK":
        raise HTTPException(status_code=500, detail="Failed to build Excel file")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


@router.post("/sales", response_model=UploadResponse)
async def upload_sales(
    file: UploadFile = File(...),
    period_year: int = Form(...),
    period_month: int = Form(...),
    upload_type: str = Form("sales"),
    stock_date: Optional[date] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC)),
) -> UploadResponse:
    try:
        result = await process_excel_upload(
            db,
            user_id=user.id,
            file=file,
            upload_type=upload_type,
            period_year=period_year,
            period_month=period_month,
            stock_date=stock_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(
        db,
        user_id=user.id,
        action="upload_excel",
        entity_type="upload_log",
        entity_id=str(result.upload_id),
        details={"status": result.status, "rows": result.processed_rows},
    )
    db.commit()
    return result


@router.post("/promo-motivation", response_model=UploadResponse)
async def upload_promo(
    file: UploadFile = File(...),
    stock_date: Optional[date] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC)),
) -> UploadResponse:
    try:
        result = await process_excel_upload(
            db,
            user_id=user.id,
            file=file,
            upload_type="promo_motivation",
            stock_date=stock_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(
        db,
        user_id=user.id,
        action="upload_promo_motivation",
        entity_type="upload_log",
        entity_id=str(result.upload_id),
    )
    db.commit()
    return result


@router.get("/templates/{template_type}")
def download_template(
    template_type: str,
    _: User = Depends(get_current_user),
) -> Response:
    """Download Excel upload templates: sales | stocks | both | promo_motivation."""
    columns = {
        "sales": ["Головной контрагент", "Артикул", "Магазин", "Количество", "Цена продажи"],
        "stocks": ["Головной контрагент", "Артикул", "Магазин", "Количество"],
        "both": ["Головной контрагент", "Артикул", "Магазин", "Количество", "Цена продажи"],
        "promo_motivation": ["Головной контрагент", "Артикул", "Магазин", "Количество"],
    }
    if template_type not in columns:
        raise HTTPException(status_code=404, detail="Unknown template")
    df = pd.DataFrame(columns=columns[template_type])
    if template_type in {"sales", "both"}:
        df.loc[0] = ["ТОО Пример", "IM-001", "ЦУМ", 1, 95000]
    else:
        df.loc[0] = ["ТОО Пример", "IM-001", "ЦУМ", 1]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Шаблон")
    return _xlsx_response(buf, f"template_{template_type}.xlsx")


@router.get("/{upload_id}/errors.xlsx")
def download_errors(
    upload_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    from app.models import UploadLog

    upload = db.get(UploadLog, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    df = pd.DataFrame(upload.errors or [])
    if df.empty:
        df = pd.DataFrame(columns=["row", "field", "message"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ошибки")
    return _xlsx_response(buf, f"errors_{upload_id}.xlsx")
