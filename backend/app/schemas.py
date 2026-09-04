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


class UserUpdate(BaseModel):
    role: Optional[str] = None
    region: Optional[str] = None
    full_name: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8)


class AuditLogOut(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CounterpartyManagerUpdate(BaseModel):
    manager_id: Optional[UUID] = None


class CounterpartyManagerBulk(BaseModel):
    counterparty_ids: list[UUID]
    manager_id: Optional[UUID] = None


class UploadErrorItem(BaseModel):
    row: int
    field: str
    message: str


class UploadResponse(BaseModel):
    upload_id: UUID
    status: str
    processed_rows: int
    errors: list[UploadErrorItem] = []


class UploadLogOut(BaseModel):
    id: UUID
    file_name: str
    upload_type: str
    status: str
    processed_rows: int
    error_count: int
    period_year: Optional[int] = None
    period_month: Optional[int] = None
    stock_date: Optional[date] = None
    created_at: Optional[datetime] = None
    user_email: Optional[str] = None
    has_file: bool = False
    has_errors: bool = False


class UploadListResponse(BaseModel):
    items: list[UploadLogOut]
    total: int


class MotivationItem(BaseModel):
    article: str
    price: Decimal
    quantity: Decimal
    grade: str
    bonus_per_unit: Decimal
    total_bonus: Decimal
    is_promo_motivation: bool = False
    name: Optional[str] = None
    lts: Optional[str] = None
    lts_date: Optional[str] = None
    counterparty: Optional[str] = None
    counterparty_id: Optional[UUID] = None


class MotivationClientRow(BaseModel):
    counterparty_id: UUID
    counterparty: str
    quantity: Decimal
    lines: int
    total_bonus: Decimal


class MotivationReport(BaseModel):
    counterparty: str
    period: str
    items: list[MotivationItem]
    total_bonus: Decimal
    counterparty_id: Optional[UUID] = None
    clients: list[MotivationClientRow] = []


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
    llm_comment: Optional[str] = None


class RecommendationsResponse(BaseModel):
    generated_at: datetime
    items: list[RecommendationItem]
    llm_status: str = "off"


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


class QuarterlyPlanBulkItem(BaseModel):
    counterparty_id: UUID
    plan_value: Decimal
    manager_id: Optional[UUID] = None


class QuarterlyPlanBulk(BaseModel):
    year: int
    quarter: int = Field(ge=1, le=4)
    items: list[QuarterlyPlanBulkItem]


class QuarterlyCommentCreate(BaseModel):
    year: int
    quarter: int = Field(ge=1, le=4)
    counterparty_id: UUID
    text: str = Field(min_length=1, max_length=4000)


class QuarterlyCommentOut(BaseModel):
    id: UUID
    counterparty_id: UUID
    year: int
    quarter: int
    text: str
    created_at: datetime
    author_name: Optional[str] = None

    model_config = {"from_attributes": True}


class DigestRunRequest(BaseModel):
    year: int
    quarter: int = Field(ge=1, le=4)
    send: bool = False


class ODataConnectionOut(BaseModel):
    source_id: str
    label: str
    base_url: str
    username: str
    password_set: bool
    verify_ssl: bool
    enabled: bool
    updated_at: Optional[str] = None


class ODataConnectionUpdate(BaseModel):
    base_url: str
    username: str
    password: Optional[str] = None  # omit or empty = keep existing
    verify_ssl: bool = False
    enabled: bool = True
    label: Optional[str] = None


class LlmSettingsOut(BaseModel):
    enabled: bool
    provider: str
    base_url: str
    model: str
    api_key_set: bool
    timeout_seconds: int
    updated_at: Optional[str] = None


class LlmSettingsUpdate(BaseModel):
    enabled: bool = False
    base_url: str
    model: str
    api_key: Optional[str] = None  # omit or empty = keep existing
    timeout_seconds: int = Field(default=20, ge=5, le=120)


class LlmSettingsTestRequest(BaseModel):
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=5, le=120)


class MailSettingsOut(BaseModel):
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    password_set: bool
    smtp_from: str
    use_tls: bool
    recipients: str
    include_quarterly: bool
    include_behind: bool
    include_recommendations: bool
    updated_at: Optional[str] = None


class MailSettingsUpdate(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: Optional[str] = None
    smtp_from: str = ""
    use_tls: bool = True
    recipients: str = ""
    include_quarterly: bool = True
    include_behind: bool = True
    include_recommendations: bool = False


class FactShipmentResult(BaseModel):
    counterparty_id: UUID
    counterparty: str
    year: int
    quarter: int
    fact_amount: Decimal
    excluded_illiquid_amount: Decimal


class CounterpartyPromoUpdate(BaseModel):
    is_promo: bool


class CounterpartyPromoBulk(BaseModel):
    counterparty_ids: list[UUID]
    is_promo: bool = True
