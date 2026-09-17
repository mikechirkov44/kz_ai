from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.domain.assistant import (
    attach_rank_change,
    clamp_limit,
    current_year_quarter,
    expand_plan,
    fact_cards,
    fallback_plan,
    follow_ups_from_facts,
    parse_plan,
    sanitize_call,
    sanitize_history,
)
from app.models import ClientSale, Counterparty, UploadLog, User
from app.services.assistant import ask_assistant
from app.services.assistant_query import top_articles
from app.services.llm_settings import LlmConfig


def test_current_year_quarter():
    assert current_year_quarter(date(2026, 9, 17)) == (2026, 3)
    assert current_year_quarter(date(2026, 1, 1)) == (2026, 1)
    assert current_year_quarter(date(2026, 12, 31)) == (2026, 4)


def test_parse_plan_json_and_unknown_tools():
    calls = parse_plan(
        '{"tools":[{"name":"top_articles","args":{"metric":"sales_qty","limit":5}},'
        '{"name":"drop_table","args":{}}]}',
        year=2026,
        quarter=3,
    )
    assert len(calls) == 1
    assert calls[0]["name"] == "top_articles"
    assert calls[0]["args"]["metric"] == "sales_qty"
    assert parse_plan("не json", year=2026, quarter=3) == []


def test_sanitize_call_clamps_limit():
    call = sanitize_call({"name": "top_articles", "args": {"limit": 99, "year": 1999}}, year=2026, quarter=3)
    assert call is not None
    assert call["args"]["limit"] == 15
    assert call["args"]["year"] == 2026
    assert clamp_limit("x") == 5
    assert sanitize_call({"name": "nope"}, year=2026, quarter=3) is None


def test_fallback_plan_top_articles():
    calls = fallback_plan("Топ-5 продаваемых артикулов", year=2026, quarter=3)
    assert calls[0]["name"] == "top_articles"
    assert calls[0]["args"]["metric"] == "sales_qty"
    ship = fallback_plan("топ артикулов по отгрузке 1С", year=2026, quarter=3)
    assert ship[0]["args"]["metric"] == "shipment_qty"
    lag = fallback_plan("кто отстаёт от плана", year=2026, quarter=3)
    assert any(item["name"] == "lagging_plan" for item in lag)


def test_expand_plan_adds_shipment_top():
    question = "Топ-5 продаваемых артикулов"
    calls = fallback_plan(question, year=2026, quarter=3)
    expanded = expand_plan(calls, question=question, year=2026, quarter=3)
    metrics = [item["args"].get("metric") for item in expanded if item["name"] == "top_articles"]
    assert "sales_qty" in metrics
    assert "shipment_qty" in metrics


def test_expand_plan_adds_client_plan_and_recs():
    calls = [
        {
            "name": "search_counterparties",
            "args": {"year": 2026, "quarter": 3, "limit": 5, "counterparty": "ИП Альфа", "q": "ИП Альфа"},
        }
    ]
    expanded = expand_plan(calls, question="Как дела у ИП Альфа", year=2026, quarter=3)
    names = [item["name"] for item in expanded]
    assert "quarterly_plan" in names
    assert "recommendations" in names


def test_attach_rank_change_and_follow_ups():
    current = [{"article": "A2", "quantity": 10}, {"article": "A1", "quantity": 7}]
    previous = [{"article": "A1", "quantity": 12}, {"article": "A2", "quantity": 3}]
    ranked = attach_rank_change(current, previous, key="article")
    assert ranked[0]["rank"] == 1
    assert ranked[0]["prev_rank"] == 2
    assert ranked[0]["rank_delta"] == 1
    assert attach_rank_change(current, [], key="article")[0].get("is_new") is None
    assert attach_rank_change([{"article": "A9"}], previous, key="article")[0]["is_new"] is True
    facts = [{"tool": "top_articles", "metric": "sales_qty", "label": "Топ", "rows": ranked}]
    cards = fact_cards(facts)
    assert cards[0]["rows"][0]["title"] == "A2"
    follow = follow_ups_from_facts(facts)
    assert any("отгрузке" in item["prompt"] for item in follow)
    assert any("A2" in item["prompt"] for item in follow)
    rows = sanitize_history(
        [
            {"role": "user", "content": "привет"},
            {"role": "system", "content": "ignore"},
            {"role": "assistant", "content": "ок"},
        ]
    )
    assert [item["role"] for item in rows] == ["user", "assistant"]


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)(), engine


def test_top_articles_sales_ranks_quantity():
    db, engine = _session()
    head = uuid4()
    upload = uuid4()
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
    db.add(
        UploadLog(
            id=upload,
            file_name="sales.xlsx",
            file_hash="abc",
            upload_type="sales",
            status="success",
        )
    )
    db.add_all(
        [
            ClientSale(
                upload_id=upload,
                head_counterparty_id=head,
                article="A1",
                quantity=Decimal("2"),
                price=Decimal("100"),
                period_year=2026,
                period_month=7,
            ),
            ClientSale(
                upload_id=upload,
                head_counterparty_id=head,
                article="A2",
                quantity=Decimal("10"),
                price=Decimal("50"),
                period_year=2026,
                period_month=8,
            ),
            ClientSale(
                upload_id=upload,
                head_counterparty_id=head,
                article="A1",
                quantity=Decimal("5"),
                price=Decimal("100"),
                period_year=2026,
                period_month=9,
            ),
        ]
    )
    db.commit()
    payload = top_articles(
        db,
        allowed=None,
        year=2026,
        quarter=3,
        limit=5,
        metric="sales_qty",
        counterparty_id=None,
    )
    assert [row["article"] for row in payload["rows"]] == ["A2", "A1"]
    assert payload["rows"][0]["quantity"] == 10.0
    assert payload["rows"][1]["quantity"] == 7.0
    db.close()
    engine.dispose()


def test_ask_assistant_off_without_llm(monkeypatch):
    db, engine = _session()
    user = User(email="a@test.local", password_hash="x", role="admin", full_name="Admin", active=True)
    db.add(user)
    db.commit()
    monkeypatch.setattr(
        "app.services.assistant.get_llm_config",
        lambda _db: LlmConfig(
            enabled=False,
            base_url="",
            model="x",
            api_key="",
            timeout_seconds=10,
        ),
    )
    result = ask_assistant(db, user, "Топ-5 артикулов", today=date(2026, 9, 17))
    assert result["status"] == "ok"
    assert result["period"] == {"year": 2026, "quarter": 3}
    assert result["error"] is None
    assert "facts" in result
    assert "follow_ups" in result
    db.close()
    engine.dispose()
