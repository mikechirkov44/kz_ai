from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import ClientSale, ClientStock, Counterparty, Nomenclature, UploadLog, User
from app.services.registers import apply_register_edit, list_register


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_register_lists_sales_and_updates_article_and_quantity():
    db = _db()
    user = User(id=uuid4(), email="admin@example.com", password_hash="x", role="admin")
    head = Counterparty(id=uuid4(), source_id="asil", onec_ref="cp", name="ТОО Азамат - Золото")
    upload = UploadLog(id=uuid4(), file_name="sales.xlsx", file_hash="h", upload_type="sales", status="success")
    old = Nomenclature(id=uuid4(), source_id="asil", onec_ref="old", article="OLD")
    new = Nomenclature(id=uuid4(), source_id="asil", onec_ref="new", article="П0581-320")
    sale = ClientSale(
        id=uuid4(),
        upload_id=upload.id,
        head_counterparty_id=head.id,
        article="OLD",
        shop="nan",
        quantity=Decimal("2"),
        price=Decimal("100"),
        period_year=2025,
        period_month=10,
    )
    stock = ClientStock(
        upload_id=upload.id,
        head_counterparty_id=head.id,
        article="OLD",
        quantity=Decimal("3"),
        stock_date=date(2025, 11, 1),
    )
    db.add_all([user, head, upload, old, new, sale, stock])
    db.commit()

    listed = list_register(db, "sales", user)
    assert listed["total"] == 1
    assert listed["items"][0]["counterparty_name"] == "ТОО Азамат - Золото"
    assert listed["items"][0]["shop"] is None
    assert list_register(db, "stocks", user)["total"] == 1

    apply_register_edit(db, sale, article="П0581-320", quantity=Decimal("4"), shop="", shop_set=True)
    db.commit()
    saved = db.scalar(select(ClientSale).where(ClientSale.id == sale.id))
    assert saved is not None
    assert saved.article == "П0581-320"
    assert saved.quantity == Decimal("4")
    assert saved.shop is None
