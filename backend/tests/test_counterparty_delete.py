from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Counterparty, Realization
from app.services.counterparty_delete import CounterpartyDeleteError, delete_counterparty


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_delete_unused_counterparty():
    db = _session()
    cp_id = uuid4()
    db.add(
        Counterparty(
            id=cp_id,
            source_id="asil",
            onec_ref="bp723",
            name="ИП Хан",
            code="БП723",
            is_folder=False,
        )
    )
    db.commit()

    payload = delete_counterparty(db, cp_id)
    db.commit()

    assert payload["code"] == "БП723"
    assert payload["name"] == "ИП Хан"
    assert db.get(Counterparty, cp_id) is None
    db.close()


def test_delete_blocked_when_realizations_exist():
    db = _session()
    cp_id = uuid4()
    db.add(
        Counterparty(
            id=cp_id,
            source_id="asil",
            onec_ref="bp490",
            name="ИП ХАН",
            code="БП490",
            is_folder=False,
        )
    )
    db.add(
        Realization(
            source_id="asil",
            onec_ref="r1",
            line_number=1,
            doc_date=date(2025, 1, 15),
            counterparty_id=cp_id,
            quantity=Decimal("1"),
            price=Decimal("100"),
            amount=Decimal("100"),
        )
    )
    db.commit()

    try:
        delete_counterparty(db, cp_id)
        raise AssertionError("expected CounterpartyDeleteError")
    except CounterpartyDeleteError as exc:
        assert "realizations=1" in str(exc)

    assert db.get(Counterparty, cp_id) is not None
    db.close()


def test_delete_missing_raises():
    db = _session()
    try:
        delete_counterparty(db, uuid4())
        raise AssertionError("expected CounterpartyDeleteError")
    except CounterpartyDeleteError as exc:
        assert str(exc) == "Контрагент не найден"
    db.close()
