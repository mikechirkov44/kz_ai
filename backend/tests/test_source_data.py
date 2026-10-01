from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    ClientOrder,
    ClientSale,
    Counterparty,
    Nomenclature,
    PromoMotivation,
    QuarterlyPlan,
    Realization,
    SyncState,
    UploadLog,
)
from app.services.source_data import clear_source_data, remove_uploads_for_source


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_remove_uploads_for_source_drops_only_that_org(tmp_path, monkeypatch):
    db = _session()
    cp = Counterparty(source_id="asil", onec_ref="c1", name="ИП А")
    db.add(cp)
    db.flush()
    gone = uuid4()
    kept = uuid4()
    db.add(UploadLog(id=gone, file_name="a.xlsx", file_hash="a", upload_type="sales", status="ok", source_id="asil"))
    db.add(UploadLog(id=kept, file_name="m.xlsx", file_hash="m", upload_type="sales", status="ok", source_id="miamor"))
    db.add(
        ClientSale(
            upload_id=gone,
            head_counterparty_id=cp.id,
            article="A1",
            quantity=Decimal("1"),
            price=Decimal("10"),
            period_year=2025,
            period_month=8,
        )
    )
    db.add(
        ClientSale(
            upload_id=kept,
            head_counterparty_id=cp.id,
            article="A2",
            quantity=Decimal("2"),
            price=Decimal("20"),
            period_year=2025,
            period_month=8,
        )
    )
    db.commit()
    paths = {gone: tmp_path / "a.xlsx", kept: tmp_path / "m.xlsx"}
    for path in paths.values():
        path.write_bytes(b"x")
    monkeypatch.setattr(
        "app.services.source_data.stored_upload_path",
        lambda file_hash, file_name: paths[gone] if file_hash == "a" else paths[kept],
    )

    counts = remove_uploads_for_source(db, "asil")
    assert counts["removed_uploads"] == 1
    assert counts["removed_sales"] == 1
    assert db.get(UploadLog, gone) is None
    assert db.get(UploadLog, kept) is not None
    assert db.scalar(select(ClientSale.id).where(ClientSale.upload_id == kept)) is not None
    assert not paths[gone].exists()
    assert paths[kept].exists()
    db.close()


def test_clear_source_data_wipes_sync_and_related_excel(tmp_path, monkeypatch):
    db = _session()
    asil_cp = Counterparty(source_id="asil", onec_ref="c1", name="ИП Асыл")
    other_cp = Counterparty(source_id="miamor", onec_ref="c2", name="ИП Миа")
    asil_nom = Nomenclature(source_id="asil", onec_ref="n1", article="A1", name="Кольцо")
    other_nom = Nomenclature(source_id="miamor", onec_ref="n2", article="B1", name="Серьги")
    db.add_all([asil_cp, other_cp, asil_nom, other_nom])
    db.flush()
    upload_id = uuid4()
    db.add(
        UploadLog(
            id=upload_id,
            file_name="sales.xlsx",
            file_hash="hash",
            upload_type="sales",
            status="ok",
            source_id="asil",
        )
    )
    db.add(
        ClientSale(
            upload_id=upload_id,
            head_counterparty_id=asil_cp.id,
            article="A1",
            quantity=Decimal("1"),
            price=Decimal("10"),
            period_year=2025,
            period_month=8,
        )
    )
    db.add(PromoMotivation(upload_id=upload_id, counterparty_id=asil_cp.id, article="A1", quantity=Decimal("1")))
    db.add(QuarterlyPlan(year=2026, quarter=1, counterparty_id=asil_cp.id, plan_value=Decimal("10")))
    db.add(
        Realization(
            source_id="asil",
            onec_ref="r1",
            line_number=1,
            doc_date=date(2025, 8, 1),
            counterparty_id=asil_cp.id,
            nomenclature_id=asil_nom.id,
            quantity=Decimal("1"),
            price=Decimal("10"),
            amount=Decimal("10"),
        )
    )
    db.add(
        ClientOrder(
            source_id="asil",
            onec_ref="o1",
            line_number=1,
            doc_date=date(2025, 8, 1),
            counterparty_id=asil_cp.id,
            nomenclature_id=asil_nom.id,
            quantity=Decimal("1"),
        )
    )
    db.add(SyncState(source_id="asil", entity="counterparties", status="idle"))
    db.add(SyncState(source_id="miamor", entity="counterparties", status="idle"))
    db.commit()
    stored = tmp_path / "sales.xlsx"
    stored.write_bytes(b"file")
    monkeypatch.setattr("app.services.source_data.stored_upload_path", lambda *_args: stored)

    counts = clear_source_data(db, "asil")

    assert counts["removed_uploads"] == 1
    assert counts["removed_sales"] == 1
    assert counts["removed_promo"] == 1
    assert counts["removed_quarterly_plans"] == 1
    assert counts["removed_realizations"] == 1
    assert counts["removed_orders"] == 1
    assert counts["removed_counterparties"] == 1
    assert counts["removed_nomenclature"] == 1
    assert counts["removed_sync_states"] == 1
    assert db.get(UploadLog, upload_id) is None
    assert db.scalar(select(Counterparty.id).where(Counterparty.source_id == "asil")) is None
    assert db.scalar(select(Counterparty.id).where(Counterparty.source_id == "miamor")) == other_cp.id
    assert db.scalar(select(Nomenclature.id).where(Nomenclature.source_id == "miamor")) == other_nom.id
    assert db.scalar(select(SyncState.id).where(SyncState.source_id == "miamor")) is not None
    assert not stored.exists()
    db.close()
