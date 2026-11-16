from datetime import date
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import ClientOrder, Counterparty, Realization, ReturnDoc
from app.services.sync import link_document_counterparties


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_link_fills_empty_counterparty_and_leaves_the_rest():
    db = _db()
    pilipets = Counterparty(id=uuid4(), source_id="asil", onec_ref="pilipets", name="ИП Пилипец М.В.")
    other = Counterparty(id=uuid4(), source_id="miamor", onec_ref="pilipets", name="Чужая база")
    kept = Counterparty(id=uuid4(), source_id="asil", onec_ref="kept", name="Уже привязан")
    db.add_all([pilipets, other, kept])

    open_real = Realization(
        id=uuid4(),
        source_id="asil",
        onec_ref="doc-621",
        line_number=1,
        doc_date=date(2026, 11, 6),
        doc_number="AS000001621",
        counterparty_onec_ref="pilipets",
        quantity=8,
        price=0,
        amount=0,
    )
    wrong_base = Realization(
        id=uuid4(),
        source_id="miamor",
        onec_ref="doc-other",
        line_number=1,
        doc_date=date(2026, 11, 6),
        doc_number="M1",
        counterparty_onec_ref="missing",
        quantity=1,
        price=0,
        amount=0,
    )
    already = Realization(
        id=uuid4(),
        source_id="asil",
        onec_ref="doc-kept",
        line_number=1,
        doc_date=date(2026, 11, 6),
        doc_number="M2",
        counterparty_id=kept.id,
        counterparty_onec_ref="pilipets",
        quantity=1,
        price=0,
        amount=0,
    )
    ret = ReturnDoc(
        id=uuid4(),
        source_id="asil",
        onec_ref="ret-1",
        line_number=1,
        doc_date=date(2026, 11, 6),
        doc_number="R1",
        counterparty_onec_ref="pilipets",
        quantity=1,
        price=0,
        amount=0,
    )
    order = ClientOrder(
        id=uuid4(),
        source_id="asil",
        onec_ref="ord-1",
        line_number=1,
        doc_date=date(2026, 11, 6),
        doc_number="O1",
        counterparty_onec_ref="pilipets",
        quantity=1,
    )
    db.add_all([open_real, wrong_base, already, ret, order])
    db.commit()

    counts = link_document_counterparties(db, "asil")
    db.commit()

    assert counts == {"realization": 1, "return_doc": 1, "client_order": 1}
    assert db.scalar(select(Realization).where(Realization.doc_number == "AS000001621")).counterparty_id == pilipets.id
    assert db.scalar(select(Realization).where(Realization.doc_number == "M1")).counterparty_id is None
    assert db.scalar(select(Realization).where(Realization.doc_number == "M2")).counterparty_id == kept.id
    assert db.scalar(select(ReturnDoc).where(ReturnDoc.doc_number == "R1")).counterparty_id == pilipets.id
    assert db.scalar(select(ClientOrder).where(ClientOrder.doc_number == "O1")).counterparty_id == pilipets.id
    db.close()
