from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user, require_roles, write_audit
from app.models import QuarterlyPlan, User
from app.schemas import (
    FactShipmentResult,
    MotivationReport,
    QuarterlyPlanUpsert,
    QuarterlyPlansReport,
    RecommendationsResponse,
    TurnoverReport,
)
from app.services.ai import generate_recommendations
from app.services.reports import (
    build_motivation_report,
    build_quarterly_plans_report,
    build_turnover_report,
    compute_fact_shipments,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/motivation", response_model=MotivationReport)
def motivation_report(
    counterparty_id: UUID,
    year: int,
    month: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MotivationReport:
    try:
        report = build_motivation_report(db, counterparty_id=counterparty_id, year=year, month=month)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    write_audit(db, user_id=user.id, action="report_motivation", details={"counterparty_id": str(counterparty_id)})
    db.commit()
    return report


@router.get("/turnover", response_model=TurnoverReport)
def turnover_report(
    view: str = Query("main", pattern="^(main|lts|counterparty|wear_type|metal_color)$"),
    year: int = Query(...),
    month: int = Query(ge=1, le=12),
    counterparty_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TurnoverReport:
    report = build_turnover_report(
        db, view=view, year=year, month=month, counterparty_id=counterparty_id
    )
    write_audit(db, user_id=user.id, action="report_turnover", details={"view": view})
    db.commit()
    return report


@router.get("/quarterly-plans", response_model=QuarterlyPlansReport)
def quarterly_plans(
    year: int,
    quarter: int = Query(ge=1, le=4),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> QuarterlyPlansReport:
    return build_quarterly_plans_report(db, year=year, quarter=quarter)


@router.post("/quarterly-plans", response_model=dict)
def upsert_quarterly_plan(
    payload: QuarterlyPlanUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC)),
) -> dict:
    existing = (
        db.query(QuarterlyPlan)
        .filter_by(year=payload.year, quarter=payload.quarter, counterparty_id=payload.counterparty_id)
        .one_or_none()
    )
    if existing:
        existing.plan_value = payload.plan_value
        existing.manager_id = payload.manager_id
    else:
        db.add(
            QuarterlyPlan(
                year=payload.year,
                quarter=payload.quarter,
                counterparty_id=payload.counterparty_id,
                plan_value=payload.plan_value,
                manager_id=payload.manager_id or user.id,
            )
        )
    db.commit()
    return {"status": "ok"}


@router.get("/fact-shipments", response_model=FactShipmentResult)
def fact_shipments(
    counterparty_id: UUID,
    year: int,
    quarter: int = Query(ge=1, le=4),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FactShipmentResult:
    try:
        return compute_fact_shipments(db, counterparty_id=counterparty_id, year=year, quarter=quarter)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/recommendations", response_model=RecommendationsResponse)
def recommendations(
    counterparty_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC, UserRole.MANAGER)),
) -> RecommendationsResponse:
    report = generate_recommendations(db, counterparty_id=counterparty_id)
    write_audit(db, user_id=user.id, action="report_recommendations")
    db.commit()
    return report
