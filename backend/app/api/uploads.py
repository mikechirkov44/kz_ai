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
from app.schemas import ManualUploadRequest, UploadFilePreview, UploadListResponse, UploadLogOut, UploadPreviewResponse, UploadResponse
from app.services.scope import is_scoped_manager
from app.services.uploads import (
    build_stored_upload_preview,
    preview_excel_uploads,
    process_excel_uploads,
    process_manual_upload,
    process_quarterly_plan_uploads,
    stored_upload_path,
)

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


def _collect_upload_files(
    file: Optional[UploadFile],
    files: Optional[list[UploadFile]],
) -> list[UploadFile]:
    out: list[UploadFile] = []
    for item in list(files or []) + ([file] if file else []):
        if item is None or not getattr(item, "filename", None):
            continue
        if item not in out:
            out.append(item)
    return out


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


@router.post("/preview", response_model=UploadPreviewResponse)
async def upload_preview(
    file: Optional[UploadFile] = File(None),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC)),
) -> UploadPreviewResponse:
    incoming = _collect_upload_files(file, files)
    if not incoming:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    try:
        return await preview_excel_uploads(db, files=incoming)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sales", response_model=UploadResponse)
async def upload_sales(
    file: Optional[UploadFile] = File(None),
    files: list[UploadFile] = File(default=[]),
    period_year: int = Form(...),
    period_month: int = Form(...),
    upload_type: str = Form("sales"),
    stock_date: Optional[date] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC)),
) -> UploadResponse:
    incoming = _collect_upload_files(file, files)
    if not incoming:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    try:
        result = await process_excel_uploads(
            db,
            user_id=user.id,
            files=incoming,
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
        details={"status": result.status, "rows": result.processed_rows, "files": len(incoming)},
    )
    db.commit()
    return result


@router.post("/promo-motivation", response_model=UploadResponse)
async def upload_promo(
    file: Optional[UploadFile] = File(None),
    files: list[UploadFile] = File(default=[]),
    stock_date: Optional[date] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC)),
) -> UploadResponse:
    incoming = _collect_upload_files(file, files)
    if not incoming:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    try:
        result = await process_excel_uploads(
            db,
            user_id=user.id,
            files=incoming,
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
        details={"files": len(incoming)},
    )
    db.commit()
    return result


@router.post("/rows", response_model=UploadResponse)
def upload_rows(
    payload: ManualUploadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC)),
) -> UploadResponse:
    try:
        result = process_manual_upload(db, user_id=user.id, payload=payload, actor=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(
        db,
        user_id=user.id,
        action="upload_manual",
        entity_type="upload_log",
        entity_id=str(result.upload_id),
        details={"status": result.status, "rows": result.processed_rows, "type": payload.upload_type},
    )
    db.commit()
    return result


@router.post("/quarterly-plans", response_model=UploadResponse)
async def upload_quarterly_plans(
    file: Optional[UploadFile] = File(None),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC, UserRole.MANAGER)
    ),
) -> UploadResponse:
    incoming = _collect_upload_files(file, files)
    if not incoming:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    try:
        result = await process_quarterly_plan_uploads(db, user_id=user.id, files=incoming, actor=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    write_audit(
        db,
        user_id=user.id,
        action="upload_quarterly_plans",
        entity_type="upload_log",
        entity_id=str(result.upload_id),
        details={"files": len(incoming)},
    )
    db.commit()
    return result


@router.get("/templates/{template_type}")
def download_template(
    template_type: str,
    _: User = Depends(get_current_user),
) -> Response:
    """Download Excel upload templates: sales | stocks | both | promo_motivation | quarterly_plans."""
    columns = {
        "sales": ["Головной контрагент", "Артикул", "Магазин", "Количество", "Цена продажи"],
        "stocks": ["Головной контрагент", "Артикул", "Магазин", "Количество"],
        "both": ["Головной контрагент", "Артикул", "Магазин", "Количество", "Цена продажи"],
        "promo_motivation": ["Контрагент", "Артикул", "Количество"],
        "quarterly_plans": ["Головной контрагент", "Год", "Квартал", "Кол-во штук"],
    }
    if template_type not in columns:
        raise HTTPException(status_code=404, detail="Unknown template")
    df = pd.DataFrame(columns=columns[template_type])
    if template_type == "quarterly_plans":
        df.loc[0] = ["ТОО Пример", 2026, 1, 20]
    elif template_type in {"sales", "both"}:
        df.loc[0] = ["ТОО Пример", "IM-001", "ЦУМ", 1, 95000]
    elif template_type == "promo_motivation":
        df.loc[0] = ["ТОО Пример", "IM-001", 1]
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


@router.get("/{upload_id}/preview", response_model=UploadFilePreview)
def preview_original(
    upload_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadFilePreview:
    upload = _require_upload(db, user, upload_id)
    try:
        return UploadFilePreview.model_validate(build_stored_upload_preview(upload))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Не удалось прочитать файл") from exc
