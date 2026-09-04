from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user, require_roles, write_audit
from app.models import QuarterlyPlan, User
from app.schemas import (
    FactShipmentResult,
    MotivationReport,
    QuarterlyCommentCreate,
    QuarterlyCommentOut,
    QuarterlyPlanBulk,
    QuarterlyPlanUpsert,
    QuarterlyPlansReport,
    RecommendationsResponse,
    TurnoverReport,
)
from app.services.ai import generate_recommendations
from app.services.llm_client import maybe_enrich_recommendations
from app.services.export_xlsx import (
    motivation_workbook,
    quarterly_plans_workbook,
    quarterly_summary_workbook,
    turnover_matrix_workbook,
    workbook_bytes,
)
from app.services.heatmap import build_dwell_heatmap
from app.services.reports import (
    build_motivation_report,
    build_quarterly_plans_report,
    build_turnover_report,
    compute_fact_shipments,
)
from app.services.scope import assert_counterparty_access, effective_manager_id, visible_counterparty_ids
from app.services.turnover_matrix import build_turnover_matrix
from app.services.quarterly_summary import (
    add_quarterly_comment,
    build_quarterly_summary,
    list_quarterly_comments,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _xlsx_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/motivation", response_model=MotivationReport)
def motivation_report(
    year: int,
    month: int = Query(ge=1, le=12),
    counterparty_id: Optional[UUID] = None,
    source_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MotivationReport:
    if counterparty_id:
        assert_counterparty_access(db, user, counterparty_id)
    try:
        report = build_motivation_report(
            db,
            year=year,
            month=month,
            counterparty_id=counterparty_id,
            source_id=source_id,
            allowed_ids=visible_counterparty_ids(db, user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    write_audit(
        db,
        user_id=user.id,
        action="report_motivation",
        details={"counterparty_id": str(counterparty_id) if counterparty_id else "all", "year": year, "month": month},
    )
    db.commit()
    return report


@router.get("/motivation.xlsx")
def motivation_export(
    year: int,
    month: int = Query(ge=1, le=12),
    counterparty_id: Optional[UUID] = None,
    source_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if counterparty_id:
        assert_counterparty_access(db, user, counterparty_id)
    try:
        report = build_motivation_report(
            db,
            year=year,
            month=month,
            counterparty_id=counterparty_id,
            source_id=source_id,
            allowed_ids=visible_counterparty_ids(db, user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    write_audit(
        db,
        user_id=user.id,
        action="export_motivation",
        details={"counterparty_id": str(counterparty_id) if counterparty_id else "all", "year": year, "month": month},
    )
    db.commit()
    return _xlsx_response(
        workbook_bytes(motivation_workbook(report)),
        f"motivation_{year}_{month:02d}.xlsx",
    )


@router.get("/turnover", response_model=TurnoverReport)
def turnover_report(
    view: str = Query("main", pattern="^(main|lts|counterparty|wear_type|metal_color)$"),
    year: int = Query(...),
    month: int = Query(ge=1, le=12),
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TurnoverReport:
    if counterparty_id:
        assert_counterparty_access(db, user, counterparty_id)
    report = build_turnover_report(
        db,
        view=view,
        year=year,
        month=month,
        counterparty_id=counterparty_id,
        manager_id=effective_manager_id(user, manager_id),
    )
    write_audit(db, user_id=user.id, action="report_turnover", details={"view": view})
    db.commit()
    return report


@router.get("/turnover-matrix")
def turnover_matrix_report(
    view: str = Query("counterparty", pattern="^(main|lts|counterparty|wear_type|metal_color)$"),
    year_from: int = Query(...),
    month_from: int = Query(ge=1, le=12),
    year_to: int = Query(...),
    month_to: int = Query(ge=1, le=12),
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Multi-month matrix matching Excel sample layouts."""
    if counterparty_id:
        assert_counterparty_access(db, user, counterparty_id)
    report = build_turnover_matrix(
        db,
        view=view,
        year_from=year_from,
        month_from=month_from,
        year_to=year_to,
        month_to=month_to,
        counterparty_id=counterparty_id,
        manager_id=effective_manager_id(user, manager_id),
    )
    write_audit(db, user_id=user.id, action="report_turnover_matrix", details={"view": view})
    db.commit()
    return report


@router.get("/turnover-matrix.xlsx")
def turnover_matrix_export(
    view: str = Query("counterparty", pattern="^(main|lts|counterparty|wear_type|metal_color)$"),
    year_from: int = Query(...),
    month_from: int = Query(ge=1, le=12),
    year_to: int = Query(...),
    month_to: int = Query(ge=1, le=12),
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if counterparty_id:
        assert_counterparty_access(db, user, counterparty_id)
    report = build_turnover_matrix(
        db,
        view=view,
        year_from=year_from,
        month_from=month_from,
        year_to=year_to,
        month_to=month_to,
        counterparty_id=counterparty_id,
        manager_id=effective_manager_id(user, manager_id),
    )
    report["view"] = view
    write_audit(db, user_id=user.id, action="export_turnover_matrix", details={"view": view})
    db.commit()
    return _xlsx_response(
        workbook_bytes(turnover_matrix_workbook(report)),
        f"turnover_{view}_{year_from}{month_from:02d}_{year_to}{month_to:02d}.xlsx",
    )


@router.get("/quarterly-plans", response_model=QuarterlyPlansReport)
def quarterly_plans(
    year: int,
    quarter: int = Query(ge=1, le=4),
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuarterlyPlansReport:
    return build_quarterly_plans_report(
        db, year=year, quarter=quarter, manager_id=effective_manager_id(user, manager_id)
    )


@router.get("/quarterly-plans.xlsx")
def quarterly_plans_export(
    year: int,
    quarter: int = Query(ge=1, le=4),
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    report = build_quarterly_plans_report(
        db, year=year, quarter=quarter, manager_id=effective_manager_id(user, manager_id)
    )
    write_audit(db, user_id=user.id, action="export_quarterly_plans", details={"year": year, "quarter": quarter})
    db.commit()
    return _xlsx_response(
        workbook_bytes(quarterly_plans_workbook(report)),
        f"quarterly_plans_{year}_Q{quarter}.xlsx",
    )


@router.get("/quarterly-summary")
def quarterly_summary(
    year: int,
    quarter: int = Query(ge=1, le=4),
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """§5.4 — метрики по блокам Цвет металла / ЖЦТ / Тип изделия + план на след. квартал."""
    if counterparty_id:
        assert_counterparty_access(db, user, counterparty_id)
    report = build_quarterly_summary(
        db,
        year=year,
        quarter=quarter,
        counterparty_id=counterparty_id,
        manager_id=effective_manager_id(user, manager_id),
    )
    write_audit(db, user_id=user.id, action="report_quarterly_summary")
    db.commit()
    return report


@router.get("/quarterly-summary.xlsx")
def quarterly_summary_export(
    year: int,
    quarter: int = Query(ge=1, le=4),
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if counterparty_id:
        assert_counterparty_access(db, user, counterparty_id)
    report = build_quarterly_summary(
        db,
        year=year,
        quarter=quarter,
        counterparty_id=counterparty_id,
        manager_id=effective_manager_id(user, manager_id),
    )
    write_audit(db, user_id=user.id, action="export_quarterly_summary", details={"year": year, "quarter": quarter})
    db.commit()
    return _xlsx_response(
        workbook_bytes(quarterly_summary_workbook(report)),
        f"quarterly_summary_{year}_Q{quarter}.xlsx",
    )


def _comment_out(db: Session, comment) -> QuarterlyCommentOut:
    author = db.get(User, comment.author_id) if comment.author_id else None
    return QuarterlyCommentOut(
        id=comment.id,
        counterparty_id=comment.counterparty_id,
        year=comment.year,
        quarter=comment.quarter,
        text=comment.text,
        created_at=comment.created_at,
        author_name=(author.full_name or author.email) if author else None,
    )


@router.get("/quarterly-comments", response_model=list[QuarterlyCommentOut])
def quarterly_comments(
    year: int,
    quarter: int = Query(ge=1, le=4),
    counterparty_id: UUID = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QuarterlyCommentOut]:
    assert_counterparty_access(db, user, counterparty_id)
    rows = list_quarterly_comments(db, year=year, quarter=quarter, counterparty_id=counterparty_id)
    return [_comment_out(db, row) for row in rows]


@router.post("/quarterly-comments", response_model=QuarterlyCommentOut)
def create_quarterly_comment(
    payload: QuarterlyCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuarterlyCommentOut:
    assert_counterparty_access(db, user, payload.counterparty_id)
    comment = add_quarterly_comment(
        db,
        year=payload.year,
        quarter=payload.quarter,
        counterparty_id=payload.counterparty_id,
        text=payload.text,
        author=user,
    )
    write_audit(
        db,
        user_id=user.id,
        action="quarterly_comment_create",
        entity_id=str(payload.counterparty_id),
        details={"year": payload.year, "quarter": payload.quarter},
    )
    db.commit()
    db.refresh(comment)
    return _comment_out(db, comment)


def _upsert_plan(db: Session, payload: QuarterlyPlanUpsert, user: User) -> QuarterlyPlan:
    existing = db.scalar(
        select(QuarterlyPlan).where(
            QuarterlyPlan.year == payload.year,
            QuarterlyPlan.quarter == payload.quarter,
            QuarterlyPlan.counterparty_id == payload.counterparty_id,
        )
    )
    if existing:
        existing.plan_value = payload.plan_value
        if payload.manager_id is not None:
            existing.manager_id = payload.manager_id
        return existing
    plan = QuarterlyPlan(
        year=payload.year,
        quarter=payload.quarter,
        counterparty_id=payload.counterparty_id,
        plan_value=payload.plan_value,
        manager_id=payload.manager_id or user.id,
    )
    db.add(plan)
    return plan


@router.post("/quarterly-plans", response_model=dict)
def upsert_quarterly_plan(
    payload: QuarterlyPlanUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC)),
) -> dict:
    plan = _upsert_plan(db, payload, user)
    write_audit(
        db,
        user_id=user.id,
        action="quarterly_plan_upsert",
        details={"counterparty_id": str(payload.counterparty_id), "year": payload.year, "quarter": payload.quarter},
    )
    db.commit()
    return {"status": "ok", "id": str(plan.id)}


@router.post("/quarterly-plans/bulk", response_model=dict)
def bulk_upsert_quarterly_plans(
    payload: QuarterlyPlanBulk,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC)),
) -> dict:
    count = 0
    for item in payload.items:
        plan_payload = QuarterlyPlanUpsert(
            year=payload.year,
            quarter=payload.quarter,
            counterparty_id=item.counterparty_id,
            plan_value=item.plan_value,
            manager_id=item.manager_id,
        )
        _upsert_plan(db, plan_payload, user)
        count += 1
    write_audit(db, user_id=user.id, action="quarterly_plan_bulk", details={"count": count})
    db.commit()
    return {"status": "ok", "upserted": count}


@router.delete("/quarterly-plans/{plan_id}", response_model=dict)
def delete_quarterly_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC)),
) -> dict:
    plan = db.get(QuarterlyPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete(plan)
    write_audit(db, user_id=user.id, action="quarterly_plan_delete", entity_id=str(plan_id))
    db.commit()
    return {"status": "ok", "deleted": str(plan_id)}


@router.delete("/quarterly-plans", response_model=dict)
def delete_quarterly_plan_by_keys(
    year: int,
    quarter: int = Query(ge=1, le=4),
    counterparty_id: UUID = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC)),
) -> dict:
    plan = db.scalar(
        select(QuarterlyPlan).where(
            QuarterlyPlan.year == year,
            QuarterlyPlan.quarter == quarter,
            QuarterlyPlan.counterparty_id == counterparty_id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete(plan)
    write_audit(
        db,
        user_id=user.id,
        action="quarterly_plan_delete",
        details={"counterparty_id": str(counterparty_id), "year": year, "quarter": quarter},
    )
    db.commit()
    return {"status": "ok"}


@router.get("/fact-shipments", response_model=FactShipmentResult)
def fact_shipments(
    counterparty_id: UUID,
    year: int,
    quarter: int = Query(ge=1, le=4),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FactShipmentResult:
    assert_counterparty_access(db, user, counterparty_id)
    try:
        return compute_fact_shipments(db, counterparty_id=counterparty_id, year=year, quarter=quarter)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/recommendations", response_model=RecommendationsResponse)
def recommendations(
    counterparty_id: Optional[UUID] = None,
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC, UserRole.MANAGER)),
) -> RecommendationsResponse:
    if counterparty_id:
        assert_counterparty_access(db, user, counterparty_id)
    report = generate_recommendations(
        db, counterparty_id=counterparty_id, manager_id=effective_manager_id(user, manager_id)
    )
    report = maybe_enrich_recommendations(db, report)
    write_audit(db, user_id=user.id, action="report_recommendations")
    db.commit()
    return report


@router.get("/dwell-heatmap")
def dwell_heatmap(
    manager_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    report = build_dwell_heatmap(db, manager_id=effective_manager_id(user, manager_id))
    write_audit(db, user_id=user.id, action="report_dwell_heatmap")
    db.commit()
    return report
