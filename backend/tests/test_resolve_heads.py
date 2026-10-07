from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Counterparty
from app.services.sync import resolve_counterparty_heads


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_resolve_counterparty_heads_links_all_bases():
    db = _db()
    asil_head = Counterparty(id=uuid4(), source_id="asil", onec_ref="h1", name="ИП Головной Асыл")
    asil_child = Counterparty(
        id=uuid4(),
        source_id="asil",
        onec_ref="c1",
        name="ИП Магазин Асыл",
        head_counterparty_onec_ref="h1",
    )
    other_head = Counterparty(id=uuid4(), source_id="base_3", onec_ref="h9", name="ИП Головной База")
    other_child = Counterparty(
        id=uuid4(),
        source_id="base_3",
        onec_ref="c9",
        name="ИП Магазин База",
        head_counterparty_onec_ref="h9",
    )
    orphan = Counterparty(
        id=uuid4(),
        source_id="asil",
        onec_ref="c2",
        name="Без головы",
        head_counterparty_onec_ref="missing",
        head_counterparty_id=uuid4(),
    )
    db.add_all([asil_head, asil_child, other_head, other_child, orphan])
    db.commit()

    counts = resolve_counterparty_heads(db)
    db.commit()

    assert counts["linked"] == 2
    assert counts["cleared"] == 1
    assert asil_child.head_counterparty_id == asil_head.id
    assert other_child.head_counterparty_id == other_head.id
    assert orphan.head_counterparty_id is None

    only_asil = resolve_counterparty_heads(db, "asil")
    assert only_asil["checked"] == 3
    db.close()
