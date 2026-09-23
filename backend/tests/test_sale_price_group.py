from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Counterparty, Nomenclature, Realization
from app.services.reports import avg_realization_price


def test_sale_price_uses_subordinate_and_price_when_amount_is_zero():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    head_id, shop_id, nom_id = uuid4(), uuid4(), uuid4()
    db.add(Counterparty(id=head_id, source_id="asil", onec_ref="head", name="ТОО Азамат - Золото"))
    db.add(
        Counterparty(
            id=shop_id,
            source_id="asil",
            onec_ref="shop",
            name="ИП Ражапова",
            head_counterparty_id=head_id,
        )
    )
    db.add(Nomenclature(id=nom_id, source_id="asil", onec_ref="nom", article="П0581-320"))
    db.add(
        Realization(
            source_id="asil",
            onec_ref="doc-shop",
            line_number=1,
            doc_date=date(2025, 7, 28),
            counterparty_id=shop_id,
            nomenclature_id=nom_id,
            quantity=Decimal("1"),
            price=Decimal("50000"),
            amount=Decimal("0"),
        )
    )
    db.add(
        Realization(
            source_id="asil",
            onec_ref="doc-head",
            line_number=1,
            doc_date=date(2024, 1, 17),
            counterparty_id=head_id,
            nomenclature_id=nom_id,
            quantity=Decimal("1"),
            price=Decimal("98391.04"),
            amount=Decimal("78713"),
        )
    )
    db.commit()

    price = avg_realization_price(db, head_id, "П0581-320")
    assert price == (Decimal("78713") + Decimal("50000")) / Decimal("2")


def test_pick_counterparty_prefers_base_with_realizations():
    from app.services.reports import pick_counterparty_for_article

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    asil_id, miamor_id, shop_id, nom_id = uuid4(), uuid4(), uuid4(), uuid4()
    db.add(Counterparty(id=asil_id, source_id="asil", onec_ref="g-asil", name="ИП Галина Р.В."))
    db.add(Counterparty(id=miamor_id, source_id="miamor", onec_ref="g-mia", name="ИП Галина Р.В."))
    db.add(
        Counterparty(
            id=shop_id,
            source_id="asil",
            onec_ref="razh",
            name="ИП Ражапова С.С.",
            head_counterparty_id=asil_id,
        )
    )
    db.add(Nomenclature(id=nom_id, source_id="asil", onec_ref="nom", article="П3536-0120"))
    db.add(
        Realization(
            source_id="asil",
            onec_ref="doc",
            line_number=1,
            doc_date=date(2025, 7, 28),
            counterparty_id=shop_id,
            nomenclature_id=nom_id,
            quantity=Decimal("1"),
            price=Decimal("100000"),
            amount=Decimal("100000"),
        )
    )
    db.commit()
    picked = pick_counterparty_for_article(
        db,
        [miamor_id, asil_id],
        article="П3536-0120",
        price=None,
    )
    assert picked == asil_id
