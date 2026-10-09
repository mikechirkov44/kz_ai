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


def test_sale_price_includes_ignore_turnover_shipments():
    """Галочка «не учитывать» режет оборачиваемость, но не цену продажи."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    head_id, shop_id, nom_id = uuid4(), uuid4(), uuid4()
    db.add(Counterparty(id=head_id, source_id="miamor", onec_ref="head", name="ИП Сайфиева И.Д."))
    db.add(
        Counterparty(
            id=shop_id,
            source_id="miamor",
            onec_ref="shop",
            name="ИП Сайфиева Татьяна Николаевна",
            head_counterparty_id=head_id,
        )
    )
    db.add(Nomenclature(id=nom_id, source_id="miamor", onec_ref="nom", article="П/137-120"))
    db.add(
        Realization(
            source_id="miamor",
            onec_ref="doc-shop",
            line_number=1,
            doc_date=date(2025, 11, 3),
            counterparty_id=shop_id,
            nomenclature_id=nom_id,
            quantity=Decimal("1"),
            price=Decimal("72456.48"),
            amount=Decimal("61588"),
            ignore_turnover=True,
        )
    )
    db.commit()
    assert avg_realization_price(db, head_id, "П/137-120") == Decimal("61588")


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
    # Even with a filled Excel price, prefer the twin that has 1C shipments.
    assert (
        pick_counterparty_for_article(
            db,
            [miamor_id, asil_id],
            article="П3536-0120",
            price=Decimal("10"),
        )
        == asil_id
    )


def test_pick_counterparty_merges_case_variants_like_khan():
    from app.services.reports import pick_counterparty_for_article, resolve_sale_price
    from app.services.uploads import _group_counterparties_by_name

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    empty_id, rich_id, nom_id = uuid4(), uuid4(), uuid4()
    empty = Counterparty(id=empty_id, source_id="asil", onec_ref="e", name="ИП Хан")
    rich = Counterparty(id=rich_id, source_id="asil", onec_ref="r", name="ИП ХАН")
    db.add_all([empty, rich])
    db.add(Nomenclature(id=nom_id, source_id="asil", onec_ref="nom", article="К3109-120"))
    db.add(
        Realization(
            source_id="asil",
            onec_ref="doc",
            line_number=1,
            doc_date=date(2026, 7, 24),
            counterparty_id=rich_id,
            nomenclature_id=nom_id,
            quantity=Decimal("1"),
            price=Decimal("100"),
            amount=Decimal("100"),
        )
    )
    db.commit()
    grouped = _group_counterparties_by_name([empty, rich])
    candidates = [item.id for item in grouped["ИП Хан"]]
    picked = pick_counterparty_for_article(db, candidates, article="К3109-120", price=Decimal("0"))
    assert picked == rich_id
    assert resolve_sale_price(db, picked, "К3109-120", Decimal("0")) is not None
