from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import ClientSale, ClientStock, Counterparty, PromoMotivation, QuarterlyPlan, UploadLog
from app.services.uploads import remove_upload


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_remove_upload_drops_its_rows_and_file(tmp_path, monkeypatch):
    db = _session()
    head = uuid4()
    gone = uuid4()
    kept = uuid4()
    db.add(
        Counterparty(
            id=head,
            source_id="asil",
            onec_ref="cp-1",
            name="ИП Альфа",
            is_folder=False,
            is_promo=True,
        )
    )
    db.add(UploadLog(id=gone, file_name="stocks.xlsx", file_hash="gone", upload_type="stocks", status="partial"))
    db.add(UploadLog(id=kept, file_name="sales.xlsx", file_hash="kept", upload_type="sales", status="success"))
    db.add(
        ClientStock(
            upload_id=gone,
            head_counterparty_id=head,
            article="A1",
            quantity=Decimal("1"),
            stock_date=date(2025, 8, 1),
        )
    )
    db.add(
        PromoMotivation(
            upload_id=gone,
            counterparty_id=head,
            article="A1",
            quantity=Decimal("1"),
        )
    )
    db.add(
        ClientSale(
            upload_id=kept,
            head_counterparty_id=head,
            article="A1",
            quantity=Decimal("2"),
            price=Decimal("100"),
            period_year=2025,
            period_month=12,
        )
    )
    db.add(
        QuarterlyPlan(
            year=2026,
            quarter=2,
            counterparty_id=head,
            plan_value=Decimal("20"),
        )
    )
    db.commit()
    stored = tmp_path / "gone_stocks.xlsx"
    stored.write_bytes(b"file")
    monkeypatch.setattr("app.services.uploads.stored_upload_path", lambda *_args: stored)

    upload = db.get(UploadLog, gone)
    assert upload is not None
    counts = remove_upload(db, upload)

    assert counts == {"removed_sales": 0, "removed_stocks": 1, "removed_promo": 1}
    assert db.get(UploadLog, gone) is None
    assert db.get(UploadLog, kept) is not None
    assert db.scalar(select(ClientStock.id)) is None
    assert db.scalar(select(PromoMotivation.id)) is None
    assert db.scalar(select(ClientSale.id)) is not None
    assert db.scalar(select(QuarterlyPlan.id)) is not None
    assert db.get(Counterparty, head).is_promo is True
    assert not stored.exists()
    db.close()


def test_remove_upload_without_file_still_drops_log(tmp_path, monkeypatch):
    db = _session()
    upload_id = uuid4()
    db.add(UploadLog(id=upload_id, file_name="missing.xlsx", file_hash="nope", upload_type="sales", status="error"))
    db.commit()
    monkeypatch.setattr("app.services.uploads.stored_upload_path", lambda *_args: tmp_path / "absent.xlsx")

    upload = db.get(UploadLog, upload_id)
    assert upload is not None
    counts = remove_upload(db, upload)

    assert counts == {"removed_sales": 0, "removed_stocks": 0, "removed_promo": 0}
    assert db.get(UploadLog, upload_id) is None
    db.close()
