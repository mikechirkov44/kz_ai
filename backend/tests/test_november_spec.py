from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException, UploadFile
import pytest

from app.api.documents import _doc_detail_realization, list_realizations
from app.api.reports import (
    MotivationRuleInput, close_motivation_through, delete_motivation_rule, import_motivation_rules,
    motivation_rules_template, save_motivation_rule,
)
from app.constants import UserRole
from app.db import Base
from app.models import (
    ClientMotivationRate, ClientMotivationRule, ClientSale, ClientStock, Counterparty, Nomenclature, Realization, UploadLog,
)
from app.services import ai
from app.services.reports import build_motivation_report
from openpyxl import load_workbook


def test_excel_motivation_import_updates_by_organization_and_rejects_partial_changes():
    def workbook(*rows):
        sheet_file = load_workbook(BytesIO(motivation_rules_template(None).body))
        for row in rows:
            sheet_file.active.append(row)
        output = BytesIO()
        sheet_file.save(output)
        output.seek(0)
        return UploadFile(output, filename="rates.xlsx")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        asil = Counterparty(source_id="asil", onec_ref="buyer", name="ИП Клиент", is_promo=True)
        miamor = Counterparty(source_id="miamor", onec_ref="buyer", name="ИП Клиент", is_promo=True)
        db.add_all([asil, miamor])
        db.commit()
        user = SimpleNamespace(role=UserRole.ADMIN, id=None)
        effective_month = date(2026, 10, 1)
        result = import_motivation_rules(workbook(
            ("Асыл", "ИП Клиент", "Мотивация только на Вывод", "10.000"),
            ("МиАмор", "ИП Клиент", "Мотивация на весь ассортимент", 5000.25),
        ), db, user, effective_month)
        assert result["imported"] == 2
        assert db.get(ClientMotivationRate, (asil.id, effective_month)).bonus == Decimal("10000")
        assert db.get(ClientMotivationRate, (miamor.id, effective_month)).bonus == Decimal("5000.25")

        assert close_motivation_through(effective_month, db, user)["closed_through"] == effective_month
        with pytest.raises(HTTPException) as import_error:
            import_motivation_rules(workbook(
                ("Асыл", "ИП Клиент", "На весь ассортимент", 6000),
            ), db, user, effective_month)
        assert import_error.value.status_code == 409
        with pytest.raises(HTTPException) as save_error:
            save_motivation_rule(asil.id, MotivationRuleInput(category="all", bonus=6000), db, user, effective_month)
        assert save_error.value.status_code == 409
        with pytest.raises(HTTPException) as delete_error:
            delete_motivation_rule(asil.id, db, user, effective_month)
        assert delete_error.value.status_code == 409

        with pytest.raises(HTTPException, match="Строка 3"):
            import_motivation_rules(workbook(
                ("Асыл", "ИП Клиент", "На весь ассортимент", 6000),
                ("МиАмор", "Другой клиент", "На весь ассортимент", 7000),
            ), db, user, effective_month)
        assert db.get(ClientMotivationRate, (asil.id, effective_month)).category == "exit"
        assert import_motivation_rules(workbook(
            ("Асыл", "ИП Клиент", "На весь ассортимент", 6000),
        ), db, user, date(2026, 11, 1))["imported"] == 1
        assert db.get(ClientMotivationRate, (asil.id, date(2026, 11, 1))).bonus == Decimal("6000")
        assert db.get(ClientMotivationRate, (asil.id, effective_month)).bonus == Decimal("10000")
        assert db.get(ClientMotivationRate, (miamor.id, effective_month)).bonus == Decimal("5000.25")


def test_motivation_rules_replace_legacy_bonus_and_use_client_source():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        client = Counterparty(source_id="asil", onec_ref="buyer", name="Buyer", is_promo=True)
        upload = UploadLog(file_name="sales", file_hash="hash", upload_type="sales", status="success")
        db.add_all([client, upload])
        db.flush()
        db.add_all([
            Nomenclature(source_id="asil", onec_ref="x", article="EXIT", lts="Вывод"),
            Nomenclature(source_id="miamor", onec_ref="x", article="REGULAR", lts="Вывод"),
            *[
                ClientSale(
                    upload_id=upload.id, head_counterparty_id=client.id, article=article,
                    quantity=2, price=100000, period_year=2026, period_month=month, is_promo_motivation=True,
                )
                for article in ("EXIT", "REGULAR")
                for month in (10, 11, 12)
            ],
        ])
        db.flush()

        def bonuses(month=10):
            report = build_motivation_report(db, year=2026, month=month, counterparty_id=client.id)
            return {item.article: item.total_bonus for item in report.items}

        standard = bonuses()
        assert standard["EXIT"] == standard["REGULAR"]
        rule = ClientMotivationRule(counterparty_id=client.id, category="exit", bonus=12345)
        db.add(rule)
        db.flush()
        assert bonuses() == {"EXIT": Decimal(24690), "REGULAR": standard["REGULAR"]}
        rule.category = "all"
        db.flush()
        assert bonuses() == {"EXIT": Decimal(24690), "REGULAR": Decimal(24690)}
        db.add_all([
            ClientMotivationRate(
                counterparty_id=client.id, effective_month=date(2026, 11, 1), category="all", bonus=3000,
            ),
            ClientMotivationRate(
                counterparty_id=client.id, effective_month=date(2026, 12, 1), category=None, bonus=None,
            ),
        ])
        db.flush()
        assert bonuses(10) == {"EXIT": Decimal(24690), "REGULAR": Decimal(24690)}
        assert bonuses(11) == {"EXIT": Decimal(6000), "REGULAR": Decimal(6000)}
        assert bonuses(12) == standard


def test_recommendations_use_company_stock_month_and_kit(monkeypatch):
    class FixedDateTime(ai.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 23, tzinfo=tz)

    monkeypatch.setattr(ai, "datetime", FixedDateTime)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        donor = Counterparty(source_id="asil", onec_ref="a", name="Donor", is_promo=True)
        recipient = Counterparty(source_id="asil", onec_ref="b", name="Recipient", is_promo=True)
        other = Counterparty(source_id="miamor", onec_ref="c", name="Other", is_promo=True)
        upload = UploadLog(file_name="sales", file_hash="hash", upload_type="sales", status="success")
        db.add_all([donor, recipient, other, upload])
        db.flush()
        for article, wear, color, kit in [
            ("OLD", "Кольцо", "Красное", None), ("HIT", "Кольцо", "Красное", "A"),
            ("PAIR", "Серьги", "Красное", "A"), ("RETURN", "Серьги", "Белое", None),
        ]:
            db.add(Nomenclature(source_id="asil", onec_ref=article, article=article, metal_color=color,
                                wear_type=wear, kit_article=kit))
        for cp, article, qty, day in [
            (donor, "OLD", 9, date(2026, 1, 1)), (donor, "OLD", 2, date(2026, 11, 1)),
            (donor, "RETURN", 1, date(2026, 1, 1)), (donor, "RETURN", 1, date(2026, 11, 1)),
            (recipient, "HIT", 1, date(2026, 11, 1)),
        ]:
            db.add(ClientStock(upload_id=upload.id, head_counterparty_id=cp.id, article=article,
                               quantity=qty, stock_date=day))
        for cp, qty in [(donor, 2), (recipient, 3), (other, 100)]:
            db.add(ClientSale(upload_id=upload.id, head_counterparty_id=cp.id, article="HIT",
                              quantity=qty, price=10, period_year=2026, period_month=10))
        db.flush()
        items = ai.generate_recommendations(db).items
        indexed = {(i.type, i.counterparty, i.article): i for i in items}
        transfer = indexed["transfer", "Donor", "OLD"]
        assert transfer.details["to_counterparty"] == "Recipient"
        assert Decimal(transfer.details["suggest_qty"]) == 2
        assert indexed["aged_return", "Donor", "RETURN"].details["replacement_articles"] == ["HIT"]
        assert indexed["kit_restock", "Recipient", "PAIR"].details["existing_article"] == "HIT"
        assert Decimal(indexed["monthly_restock", "Recipient", "HIT"].details["suggest_qty"]) == 3


def test_realization_detail_resolves_saved_key_in_same_company():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        class BoolOr:
            value = False

            def step(self, value):
                self.value = self.value or bool(value)

            def finalize(self):
                return self.value

        db.connection().connection.driver_connection.create_aggregate("bool_or", 1, BoolOr)
        db.add_all([
            Counterparty(source_id="asil", onec_ref="buyer", name="ИП Жауханова"),
            Counterparty(source_id="miamor", onec_ref="buyer", name="Другая база"),
        ])
        sale = Realization(
            source_id="asil", onec_ref="doc", line_number=1, doc_date=date(2026, 11, 3),
            doc_number="AS000001607", counterparty_onec_ref="buyer", quantity=1, price=1, amount=1,
        )
        db.add(sale)
        db.flush()
        assert _doc_detail_realization(db, [sale])["counterparty"] == "ИП Жауханова"
        report = list_realizations(
            source_id="asil", q="Жауханова", page=1, page_size=50, db=db,
            user=SimpleNamespace(role=UserRole.ADMIN),
        )
        assert report["total"] == 1
        assert report["items"][0]["counterparty"] == "ИП Жауханова"
