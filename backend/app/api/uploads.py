from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
import io
import pandas as pd

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user, require_roles, write_audit
from app.models import UploadLog, User
from app.schemas import UploadListResponse, UploadLogOut, UploadResponse
from app.services.scope import is_scoped_manager
from app.services.uploads import process_excel_upload, stored_upload_path

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
            actor=user,
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
            actor=user,
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


def _require_upload(db: Session, user: User, upload_id: UUID) -> UploadLog:
    upload = db.get(UploadLog, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    if is_scoped_manager(user) and upload.user_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этой загрузке")
    return upload


@router.get("", response_model=UploadListResponse)
@router.get("/", response_model=UploadListResponse)
def list_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadListResponse:
    filters = []
    if is_scoped_manager(user):
        filters.append(UploadLog.user_id == user.id)
    total = db.scalar(select(func.count(UploadLog.id)).where(*filters)) or 0
    rows = db.execute(
        select(UploadLog, User.email)
        .outerjoin(User, User.id == UploadLog.user_id)
        .where(*filters)
        .order_by(UploadLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for upload, email in rows:
        errors = upload.errors or []
        items.append(
            UploadLogOut(
                id=upload.id,
                file_name=upload.file_name,
                upload_type=upload.upload_type,
                status=upload.status,
                processed_rows=upload.processed_rows,
                error_count=len(errors),
                period_year=upload.period_year,
                period_month=upload.period_month,
                stock_date=upload.stock_date,
                created_at=upload.created_at,
                user_email=email,
                has_file=stored_upload_path(upload.file_hash, upload.file_name).is_file(),
                has_errors=bool(errors),
            )
        )
    return UploadListResponse(items=items, total=total)


@router.get("/{upload_id}/file")
def download_original(
    upload_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    upload = _require_upload(db, user, upload_id)
    path = stored_upload_path(upload.file_hash, upload.file_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл уже нет на диске")
    return FileResponse(
        path,
        filename=upload.file_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/{upload_id}/errors.xlsx")
def download_errors(
    upload_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    upload = _require_upload(db, user, upload_id)
    df = pd.DataFrame(upload.errors or [])
    if df.empty:
        df = pd.DataFrame(columns=["row", "field", "message"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ошибки")
    return _xlsx_response(buf, f"errors_{upload_id}.xlsx")
