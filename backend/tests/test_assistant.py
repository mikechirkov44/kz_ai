from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.domain.assistant import (
    ONEC_TOOLS,
    attach_rank_change,
    clamp_limit,
    current_year_quarter,
    expand_plan,
    fact_cards,
    fallback_plan,
    extract_onec_search,
    fallback_plan_onec,
    follow_ups_from_facts,
    looks_like_prompt_leak,
    normalize_mode,
    onec_direct_answer,
    parse_plan,
    sanitize_call,
    sanitize_history,
)
from app.odata.client import ODataSource
from app.services.assistant_odata import build_odata_filter, query_odata_live
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
    assert result["mode"] == "service"
    assert result["error"] is None
    assert "facts" in result
    assert "follow_ups" in result
    db.close()
    engine.dispose()


def test_normalize_mode_and_sanitize_odata():
    assert normalize_mode("1С") == "onec"
    assert normalize_mode("service") == "service"
    assert sanitize_call({"name": "odata_live", "args": {}}, year=2026, quarter=3) is None
    call = sanitize_call(
        {"name": "odata_live", "args": {"entity": "drop", "source": "x", "limit": 99}},
        year=2026,
        quarter=3,
        allowed_tools=ONEC_TOOLS,
    )
    assert call is not None
    assert call["args"]["entity"] == "realization"
    assert call["args"]["source"] == "all"
    assert call["args"]["limit"] == 30


def test_parse_plan_onec_drops_service_tools():
    calls = parse_plan(
        '{"tools":[{"name":"top_articles","args":{}},{"name":"odata_live","args":{"entity":"client_order"}}]}',
        year=2026,
        quarter=3,
        allowed_tools=ONEC_TOOLS,
    )
    assert len(calls) == 1
    assert calls[0]["name"] == "odata_live"
    assert calls[0]["args"]["entity"] == "client_order"


def test_fallback_plan_onec_and_expand():
    orders = fallback_plan_onec("какие заказы есть", year=2026, quarter=3)
    assert orders[0]["args"]["entity"] == "client_order"
    noms = fallback_plan_onec("номенклатура кольцо", year=2026, quarter=3)
    assert noms[0]["args"]["entity"] == "nomenclature"
    asil = fallback_plan_onec("реализации по Асыл", year=2026, quarter=3)
    assert asil[0]["args"]["entity"] == "realization"
    assert asil[0]["args"]["source"] == "asil"
    top = fallback_plan_onec("топ-5 клиентов из обеих баз", year=2026, quarter=3)
    assert top[0]["args"]["entity"] == "realization"
    assert top[0]["args"].get("aggregate") == "counterparties"
    catalog = fallback_plan_onec("найди контрагента Альфа", year=2026, quarter=3)
    assert catalog[0]["args"]["entity"] == "counterparty"
    oldest = fallback_plan_onec("выведи самую старую карточку артикула", year=2026, quarter=3)
    assert oldest[0]["args"]["entity"] == "nomenclature"
    assert oldest[0]["args"]["order"] == "oldest"
    assert "q" not in oldest[0]["args"]
    assert extract_onec_search("выведи самую старую карточку артикула") is None
    assert extract_onec_search("найди кольцо") == "кольцо"
    expanded = expand_plan(orders, question="заказы", year=2026, quarter=3, mode="onec")
    assert expanded == orders
    rewritten = expand_plan(
        [{"name": "odata_live", "args": {"entity": "counterparty", "q": "топ-5", "year": 2026, "quarter": 3, "limit": 15}}],
        question="топ-5 клиентов",
        year=2026,
        quarter=3,
        mode="onec",
    )
    assert rewritten[0]["args"]["entity"] == "realization"
    assert "q" not in rewritten[0]["args"]
    follow = follow_ups_from_facts([{"tool": "odata_live", "entity": "realization", "rows": []}], mode="onec")
    assert any("Возврат" in item["label"] for item in follow)
    assert all("Excel" not in item["prompt"] for item in follow)


def test_build_odata_filter_skips_date():
    filt = build_odata_filter("realization")
    assert filt == "Posted eq true"
    assert "Date" not in filt
    scoped = build_odata_filter("realization", counterparty_ref="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert "Контрагент_Key eq guid'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'" in scoped
    catalog = build_odata_filter("nomenclature", q="кольцо")
    assert "substringof('кольцо',Description)" in catalog
    assert "DeletionMark" not in catalog
    assert "Date" not in catalog
    assert build_odata_filter("nomenclature") == ""


class _FakeOData:
    def __init__(self, source: ODataSource, rows: list[dict], total: int | None = None) -> None:
        self.source = source
        self.rows = rows
        self.total = len(rows) if total is None else total
        self.start_skip: int | None = None

    def __enter__(self) -> "_FakeOData":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def entity_count(self, entity_set: str, *, filter_expr: str | None = None) -> int:
        return self.total

    def fetch_all(self, entity_set: str, **kwargs: object) -> list[dict]:
        assert "Date ge" not in str(kwargs.get("filter_expr") or "")
        self.start_skip = int(kwargs.get("start_skip") or 0)
        return self.rows


def test_query_odata_live_keeps_quarter_rows(monkeypatch):
    db, engine = _session()
    user = User(email="m@test.local", password_hash="x", role="admin", full_name="A", active=True)
    db.add(user)
    db.commit()
    source = ODataSource(source_id="asil", base_url="http://1c.local", username="u", password="p")
    monkeypatch.setattr("app.services.assistant_odata.configured_sources", lambda _db: [source])
    rows = [
        {
            "Ref_Key": "d1",
            "Number": "Р-1",
            "Date": "2026-08-10T00:00:00",
            "Posted": True,
            "DeletionMark": False,
        },
        {
            "Ref_Key": "d2",
            "Number": "Р-2",
            "Date": "2026-01-10T00:00:00",
            "Posted": True,
            "DeletionMark": False,
        },
    ]
    fake = _FakeOData(source, rows, total=80)
    payload = query_odata_live(
        db,
        user,
        {"year": 2026, "quarter": 3, "limit": 10, "entity": "realization", "source": "all"},
        client_factory=lambda _src: fake,
    )
    assert [row["number"] for row in payload["rows"]] == ["Р-1"]
    assert payload["entity"] == "realization"
    assert fake.start_skip == 40
    oldest_rows = [
        {
            "Ref_Key": "n1",
            "Description": "Кольцо старое",
            "Артикул": "A1",
            "DeletionMark": False,
            "IsFolder": False,
        }
    ]
    oldest_fake = _FakeOData(source, oldest_rows, total=80)
    oldest = query_odata_live(
        db,
        user,
        {
            "year": 2026,
            "quarter": 3,
            "limit": 10,
            "entity": "nomenclature",
            "source": "all",
            "order": "oldest",
        },
        client_factory=lambda _src: oldest_fake,
    )
    assert oldest_fake.start_skip == 0
    assert oldest["rows"][0]["article"] == "A1"
    assert oldest["order"] == "oldest"
    mixed = [
        {
            "Ref_Key": "dead",
            "Description": "Удалено",
            "Артикул": "X",
            "DeletionMark": True,
            "IsFolder": False,
        },
        {
            "Ref_Key": "n2",
            "Description": "Живое",
            "Артикул": "B2",
            "DeletionMark": False,
            "IsFolder": False,
        },
    ]
    mixed_fake = _FakeOData(source, mixed, total=2)
    live = query_odata_live(
        db,
        user,
        {"year": 2026, "quarter": 3, "limit": 10, "entity": "nomenclature", "source": "all", "order": "oldest"},
        client_factory=lambda _src: mixed_fake,
    )
    assert [row["article"] for row in live["rows"]] == ["B2"]
    db.close()
    engine.dispose()


def test_looks_like_prompt_leak():
    assert looks_like_prompt_leak(
        "We need answer Russian concise manager style. Facts have two JSON sources. Don't invent."
    )
    assert looks_like_prompt_leak("Цифры только из JSON фактов. Не выдумывай артикулы.")
    assert not looks_like_prompt_leak("Топ Excel: 00000797 — 1 900 шт. Отгрузки 1С ниже.")


def test_ask_assistant_onec_without_llm(monkeypatch):
    db, engine = _session()
    user = User(email="c@test.local", password_hash="x", role="admin", full_name="Admin", active=True)
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
    result = ask_assistant(db, user, "Покажи реализации", mode="onec", today=date(2026, 9, 17))
    assert result["status"] == "ok"
    assert result["mode"] == "onec"
    assert result["tools"][0]["name"] == "odata_live"
    assert "живой 1С" in result["answer"] or "1С" in result["answer"]
    db.close()
    engine.dispose()


def test_onec_direct_answer_skips_llm_on_error_and_ranking():
    empty = onec_direct_answer(
        [{"tool": "odata_live", "entity": "realization", "error": "Нет включённых подключений 1С", "rows": []}],
        question="топ-5 клиентов из обеих баз",
    )
    assert empty == "Нет включённых подключений 1С"
    ranked = onec_direct_answer(
        [
            {
                "tool": "odata_live",
                "label": "Реализации 1С",
                "entity": "realization",
                "period": "2026 Q3",
                "rows": [{"title": "Р-1", "number": "Р-1", "counterparty": "ИП Альфа"}],
            }
        ],
        question="топ-5 клиентов из обеих баз",
    )
    assert ranked is not None
    assert "ИП Альфа" in ranked
    listing = onec_direct_answer(
        [
            {
                "tool": "odata_live",
                "label": "Реализации 1С",
                "entity": "realization",
                "rows": [{"title": "Р-1", "number": "Р-1"}],
            }
        ],
        question="Покажи реализации за квартал",
    )
    assert listing is not None
    assert "Р-1" in listing


def test_ask_assistant_onec_empty_does_not_call_answer_llm(monkeypatch):
    db, engine = _session()
    user = User(email="d@test.local", password_hash="x", role="admin", full_name="Admin", active=True)
    db.add(user)
    db.commit()
    monkeypatch.setattr(
        "app.services.assistant.get_llm_config",
        lambda _db: LlmConfig(
            enabled=True,
            base_url="http://llm",
            model="x",
            api_key="k",
            timeout_seconds=10,
        ),
    )
    calls: list[int] = []

    def fake_chat(*_args, **_kwargs):
        calls.append(1)
        return '{"tools":[{"name":"odata_live","args":{"entity":"counterparty"}}]}', ""

    monkeypatch.setattr("app.services.assistant.complete_chat", fake_chat)
    result = ask_assistant(db, user, "топ-5 клиентов из обеих баз", mode="onec", today=date(2026, 9, 17))
    assert result["status"] == "ok"
    assert "JSON" not in result["answer"]
    assert "Excel" not in result["answer"]
    assert len(calls) == 1
    db.close()
    engine.dispose()


def test_ask_assistant_replaces_prompt_leak(monkeypatch):
    db, engine = _session()
    user = User(email="e@test.local", password_hash="x", role="admin", full_name="Admin", active=True)
    db.add(user)
    db.commit()
    monkeypatch.setattr(
        "app.services.assistant.get_llm_config",
        lambda _db: LlmConfig(
            enabled=True,
            base_url="http://llm",
            model="x",
            api_key="k",
            timeout_seconds=10,
        ),
    )

    def fake_chat(_config, messages, **_kwargs):
        system = messages[0]["content"]
        if "маршрутизатор" in system:
            return '{"tools":[{"name":"top_articles","args":{"metric":"sales_qty"}}]}', ""
        return "We need answer Russian. Facts have JSON. Don't invent Excel totals.", ""

    monkeypatch.setattr("app.services.assistant.complete_chat", fake_chat)
    result = ask_assistant(db, user, "Топ-5 продаваемых артикулов", today=date(2026, 9, 17))
    assert result["status"] == "ok"
    assert "JSON" not in result["answer"]
    assert "Don't invent" not in result["answer"]
    db.close()
    engine.dispose()
