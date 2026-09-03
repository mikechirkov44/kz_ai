from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(64), index=True)
    region: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Nomenclature(Base, TimestampMixin):
    __tablename__ = "nomenclature"
    __table_args__ = (
        UniqueConstraint("source_id", "onec_ref", name="uq_nomenclature_source_ref"),
        Index("ix_nomenclature_article", "article"),
        Index("ix_nomenclature_barcode", "barcode"),
        Index("ix_nomenclature_lts", "lts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    onec_ref: Mapped[str] = mapped_column(String(64))
    article: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    assay: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metal_color: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    wear_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lts: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lts_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    characteristics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_promo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_weighted: Mapped[bool] = mapped_column(Boolean, default=False)
    modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Counterparty(Base, TimestampMixin):
    __tablename__ = "counterparty"
    __table_args__ = (
        UniqueConstraint("source_id", "onec_ref", name="uq_counterparty_source_ref"),
        Index("ix_counterparty_head", "head_counterparty_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    onec_ref: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(512))
    head_counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparty.id"), nullable=True
    )
    head_counterparty_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    parent_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_folder: Mapped[bool] = mapped_column(Boolean, default=False)
    is_promo: Mapped[bool] = mapped_column(Boolean, default=False)
    work_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    work_type_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    shops: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class Realization(Base, TimestampMixin):
    __tablename__ = "realization"
    __table_args__ = (
        UniqueConstraint("source_id", "onec_ref", "line_number", name="uq_realization_line"),
        Index("ix_realization_cp_date", "counterparty_id", "doc_date"),
        Index("ix_realization_nom_date", "nomenclature_id", "doc_date"),
        Index("ix_realization_warehouse", "warehouse"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    onec_ref: Mapped[str] = mapped_column(String(64))
    line_number: Mapped[int] = mapped_column(Integer, default=1)
    doc_date: Mapped[date] = mapped_column(Date, index=True)
    doc_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparty.id"), nullable=True
    )
    nomenclature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nomenclature.id"), nullable=True
    )
    counterparty_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nomenclature_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ignore_turnover: Mapped[bool] = mapped_column(Boolean, default=False)
    series: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class ReturnDoc(Base, TimestampMixin):
    __tablename__ = "return_doc"
    __table_args__ = (
        UniqueConstraint("source_id", "onec_ref", "line_number", name="uq_return_line"),
        Index("ix_return_cp_date", "counterparty_id", "doc_date"),
        Index("ix_return_nom_date", "nomenclature_id", "doc_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    onec_ref: Mapped[str] = mapped_column(String(64))
    line_number: Mapped[int] = mapped_column(Integer, default=1)
    doc_date: Mapped[date] = mapped_column(Date, index=True)
    doc_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparty.id"), nullable=True
    )
    nomenclature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nomenclature.id"), nullable=True
    )
    counterparty_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nomenclature_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ignore_turnover: Mapped[bool] = mapped_column(Boolean, default=False)
    series: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class ClientOrder(Base, TimestampMixin):
    __tablename__ = "client_order"
    __table_args__ = (UniqueConstraint("source_id", "onec_ref", "line_number", name="uq_client_order_line"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    onec_ref: Mapped[str] = mapped_column(String(64))
    line_number: Mapped[int] = mapped_column(Integer, default=1)
    doc_date: Mapped[date] = mapped_column(Date, index=True)
    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparty.id"), nullable=True
    )
    nomenclature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nomenclature.id"), nullable=True
    )
    counterparty_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nomenclature_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_counterparty_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)
    series: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class ProductionReceipt(Base, TimestampMixin):
    __tablename__ = "production_receipt"
    __table_args__ = (UniqueConstraint("source_id", "onec_ref", "line_number", name="uq_production_receipt_line"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    onec_ref: Mapped[str] = mapped_column(String(64))
    line_number: Mapped[int] = mapped_column(Integer, default=1)
    doc_date: Mapped[date] = mapped_column(Date, index=True)
    nomenclature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nomenclature.id"), nullable=True
    )
    nomenclature_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    series: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    client_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_order.id"), nullable=True
    )
    client_order_onec_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(64), default="production")


class UploadLog(Base, TimestampMixin):
    __tablename__ = "upload_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    file_name: Mapped[str] = mapped_column(String(512))
    file_hash: Mapped[str] = mapped_column(String(128))
    upload_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[Optional[list[Any]]] = mapped_column(JSON, nullable=True)
    period_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    period_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stock_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class ClientSale(Base):
    __tablename__ = "client_sales"
    __table_args__ = (Index("ix_client_sales_period", "head_counterparty_id", "period_year", "period_month"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("upload_log.id"), index=True)
    head_counterparty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparty.id"))
    article: Mapped[str] = mapped_column(String(128), index=True)
    shop: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    period_year: Mapped[int] = mapped_column(Integer)
    period_month: Mapped[int] = mapped_column(Integer)
    is_promo_motivation: Mapped[bool] = mapped_column(Boolean, default=False)


class ClientStock(Base):
    __tablename__ = "client_stocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("upload_log.id"), index=True)
    head_counterparty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparty.id"))
    article: Mapped[str] = mapped_column(String(128), index=True)
    shop: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    stock_date: Mapped[date] = mapped_column(Date, index=True)


class PromoMotivation(Base):
    __tablename__ = "promo_motivation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("upload_log.id"), index=True)
    counterparty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparty.id"))
    article: Mapped[str] = mapped_column(String(128), index=True)
    shop: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    stock_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class QuarterlyPlan(Base, TimestampMixin):
    __tablename__ = "quarterly_plan"
    __table_args__ = (UniqueConstraint("year", "quarter", "counterparty_id", name="uq_quarterly_plan"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)
    counterparty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("counterparty.id"))
    plan_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class SyncState(Base, TimestampMixin):
    __tablename__ = "sync_state"
    __table_args__ = (UniqueConstraint("source_id", "entity", name="uq_sync_state"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(32))
    entity: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="idle")
    last_incremental_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_full_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rows_synced: Mapped[int] = mapped_column(Integer, default=0)
