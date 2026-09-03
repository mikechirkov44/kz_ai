from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    region: Optional[str] = None
    full_name: Optional[str] = None
    active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str
    region: Optional[str] = None
    full_name: Optional[str] = None


class UploadErrorItem(BaseModel):
    row: int
    field: str
    message: str


class UploadResponse(BaseModel):
    upload_id: UUID
    status: str
    processed_rows: int
    errors: list[UploadErrorItem] = []


class MotivationItem(BaseModel):
    article: str
    price: Decimal
    quantity: Decimal
    grade: str
    bonus_per_unit: Decimal
    total_bonus: Decimal
    is_promo_motivation: bool = False


class MotivationReport(BaseModel):
    counterparty: str
    period: str
    items: list[MotivationItem]
    total_bonus: Decimal


class TurnoverRow(BaseModel):
    counterparty: Optional[str] = None
    dimension: Optional[str] = None
    work_type: Optional[str] = None
    work_type_percent: Optional[Decimal] = None
    sales: Decimal
    stock_begin: Decimal
    stock_end: Decimal
    stock_avg: Decimal
    turnover_percent: Decimal
    proposal: Optional[Decimal] = None


class TurnoverReport(BaseModel):
    period: str
    view: str
    data: list[TurnoverRow]


class QuarterlyClientRow(BaseModel):
    counterparty: str
    counterparty_id: UUID
    plan: Decimal
    fact: Decimal
    percent: Decimal
    dynamics: Optional[Decimal] = None


class QuarterlyPlansReport(BaseModel):
    year: int
    quarter: int
    clients: list[QuarterlyClientRow]


class SyncStateOut(BaseModel):
    source_id: str
    entity: str
    status: str
    last_incremental_at: Optional[datetime] = None
    last_full_at: Optional[datetime] = None
    last_error: Optional[str] = None
    rows_synced: int

    model_config = {"from_attributes": True}


class RecommendationItem(BaseModel):
    type: str
    severity: str
    counterparty: Optional[str] = None
    article: Optional[str] = None
    message: str
    details: dict[str, Any] = {}


class RecommendationsResponse(BaseModel):
    generated_at: datetime
    items: list[RecommendationItem]


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    odata: dict[str, str]


class QuarterlyPlanUpsert(BaseModel):
    year: int
    quarter: int = Field(ge=1, le=4)
    counterparty_id: UUID
    plan_value: Decimal
    manager_id: Optional[UUID] = None


class FactShipmentResult(BaseModel):
    counterparty_id: UUID
    counterparty: str
    year: int
    quarter: int
    fact_amount: Decimal
    excluded_illiquid_amount: Decimal
