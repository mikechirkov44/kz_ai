import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx

from app.domain.llm_enrich import (
    apply_llm_cell_texts,
    apply_llm_comments,
    build_cell_enrich_messages,
    build_enrich_messages,
    build_llm_digest,
    cell_rules_have_facts,
    chat_completions_url,
    collect_matrix_cell_payload,
    compact_recommendation_payload,
    parse_llm_cell_texts,
    parse_llm_comments,
    parse_llm_report,
    parse_llm_summary,
    slice_for_enrichment,
)
from app.schemas import RecommendationItem, RecommendationsResponse
from app.services.llm_client import (
    check_llm_connection,
    enrich_recommendation_items,
    maybe_enrich_quarterly_summary,
    maybe_enrich_recommendations,
)
from app.services.llm_settings import LlmConfig, settings_public_view


def test_chat_completions_url_variants():
    assert chat_completions_url("https://api.openai.com/v1") == "https://api.openai.com/v1/chat/completions"
    assert chat_completions_url("https://api.openai.com/v1/") == "https://api.openai.com/v1/chat/completions"
    assert chat_completions_url("https://api.openai.com") == "https://api.openai.com/v1/chat/completions"
    assert (
        chat_completions_url("http://localhost:11434/v1/chat/completions")
        == "http://localhost:11434/v1/chat/completions"
    )
    assert chat_completions_url("  ") == ""


def test_parse_llm_comments_object_and_markdown():
    raw = """```json
{"comments":[{"index":1,"comment":" Вернуть артикул "},{"index":0,"comment":"Сверить остаток"}]}
```"""
    comments = parse_llm_comments(raw, 2)
    assert comments == ["Сверить остаток", "Вернуть артикул"]


def test_parse_llm_comments_list_and_invalid():
    assert parse_llm_comments('["А", "Б"]', 2) == ["А", "Б"]
    assert parse_llm_comments("not-json", 2) == [None, None]
    assert parse_llm_comments('{"comments":[{"index":9,"comment":"x"}]}', 1) == [None]
    assert parse_llm_comments("", 0) == []


def test_apply_and_slice_and_payload():
    items = [
        {"type": "illiquid", "severity": "high", "message": "A"},
        {"type": "pattern", "severity": "low", "message": "B"},
    ]
    sliced = slice_for_enrichment(items, 1)
    assert sliced == items[:1]
    payload = compact_recommendation_payload(items)
    assert payload[0]["index"] == 0
    enriched = apply_llm_comments(items, ["Сделать возврат", None])
    assert enriched[0]["llm_comment"] == "Сделать возврат"
    assert "llm_comment" not in enriched[1]
    messages = build_enrich_messages(items)
    assert messages[0]["role"] == "system"
    assert "digest.playbook" in messages[0]["content"]
    user = json.loads(messages[1]["content"])
    assert user["items"][1]["message"] == "B"
    assert user["digest"]["total"] == 2
    assert "playbook" in user["digest"]
    priced = compact_recommendation_payload(
        [
            {
                "type": "price_arbitrage",
                "message": "Цена",
                "details": {
                    "articles": [{"article": "R-1", "gap_percent": "31.04", "client_avg_price": "120000"}],
                },
            }
        ]
    )
    assert priced[0]["details"]["articles"][0] == {"article": "R-1", "gap_percent": 31.0, "client_avg_price": 120000.0}


def _config(**kwargs) -> LlmConfig:
    data = dict(
        enabled=True,
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
        timeout_seconds=10,
    )
    data.update(kwargs)
    return LlmConfig(**data)


def test_llm_test_connection_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["Authorization"] == "Bearer sk-test"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = check_llm_connection(_config(), client=client)
    assert result["status"] == "ok"


def test_llm_test_connection_http_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = check_llm_connection(_config(), client=client)
    assert result["status"] == "error"
    assert "unauthorized" in result["detail"]


def test_llm_test_connection_network_error():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = check_llm_connection(_config(), client=client)
    assert result["status"] == "error"


def test_llm_test_connection_empty_url():
    result = check_llm_connection(_config(base_url=""))
    assert result["status"] == "error"


def test_enrich_items_empty_skips_http():
    items, status, summary, report = enrich_recommendation_items([], _config())
    assert items == []
    assert status == "ok"
    assert summary is None
    assert report is None


def test_enrich_items_attaches_comments():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "gpt-4o-mini"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"Начните с возврата.","comments":[{"index":0,"comment":"Обменять SKU"}]}'
                        }
                    }
                ]
            },
        )

    items = [RecommendationItem(type="illiquid", severity="high", message="Вернуть артикул X")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status, summary, report = enrich_recommendation_items(items, _config(), client=client)
    assert status == "ok"
    assert enriched[0].message == "Вернуть артикул X"
    assert enriched[0].llm_comment == "Обменять SKU"
    assert summary == "Начните с возврата."
    assert report and report["situation"] == "Начните с возврата."


def test_enrich_items_unparseable_content():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "просто текст"}}]})

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status, summary, report = enrich_recommendation_items(items, _config(), client=client)
    assert status == "error"
    assert enriched[0].llm_comment is None
    assert summary is None
    assert report is None


def test_enrich_items_empty_url():
    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    enriched, status, summary, report = enrich_recommendation_items(items, _config(base_url=""))
    assert status == "error"
    assert enriched[0].message == "keep"
    assert summary is None
    assert report is None


def test_enrich_items_fallback_on_bad_response():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status, summary, report = enrich_recommendation_items(items, _config(), client=client)
    assert status == "error"
    assert enriched[0].llm_comment is None
    assert enriched[0].message == "keep"
    assert summary is None
    assert report is None


def test_maybe_enrich_ok_and_exception(monkeypatch):
    report = RecommendationsResponse(
        generated_at=datetime.now(timezone.utc),
        items=[RecommendationItem(type="illiquid", severity="high", message="keep")],
    )
    monkeypatch.setattr(
        "app.services.llm_client.get_llm_config",
        lambda _db: _config(),
    )

    def boom(*_args, **_kwargs):
        raise RuntimeError("crash")

    monkeypatch.setattr("app.services.llm_client.enrich_recommendation_items", boom)
    out = maybe_enrich_recommendations(object(), report)
    assert out.llm_status == "error"
    assert out.items[0].message == "keep"


def test_maybe_enrich_applies_summary(monkeypatch):
    report = RecommendationsResponse(
        generated_at=datetime.now(timezone.utc),
        items=[RecommendationItem(type="illiquid", severity="high", message="keep")],
        summary="Правила",
    )
    monkeypatch.setattr("app.services.llm_client.get_llm_config", lambda _db: _config())

    def fake_enrich(items, _config, **_kwargs):
        items[0].llm_comment = "Совет"
        return items, "ok", "Сводка модели", {"headline": "Сводка", "situation": "Сводка модели", "notes": {}}

    monkeypatch.setattr("app.services.llm_client.enrich_recommendation_items", fake_enrich)
    out = maybe_enrich_recommendations(object(), report)
    assert out.llm_status == "ok"
    assert out.summary == "Сводка модели"
    assert out.items[0].llm_comment == "Совет"


def test_parse_llm_summary():
    assert parse_llm_summary('{"summary":" Сначала возврат ","comments":[]}') == "Сначала возврат"
    assert parse_llm_summary('["нет"]') is None
    assert parse_llm_summary("не json") is None


def test_build_digest_and_parse_report():
    digest = build_llm_digest(
        [
            {
                "action": "return",
                "type": "mix",
                "severity": "high",
                "counterparty": "A",
                "score": 95,
                "title": "Верните 8 шт.",
                "details": {
                    "suggest_qty": "8",
                    "plan_percent": "12",
                    "months_without_sales": 9,
                    "wear_type": "Кольцо",
                    "lts": "Вывод",
                },
            },
            {
                "action": "reprice",
                "type": "price_arbitrage",
                "severity": "medium",
                "counterparty": "B",
                "score": 40,
                "title": "Цена",
                "details": {"gap_percent": "12.5", "wear_type": "Серьги", "plan_percent": "80"},
            },
        ]
    )
    assert digest["total"] == 2
    assert digest["actions"]["return"] == 1
    assert digest["max_price_gap"] == 12.5
    assert digest["mix_count"] == 1
    assert digest["exit_lts"] == 1
    assert digest["behind_plan"] == 1
    assert digest["playbook"][0]["counterparty"] == "A"
    assert digest["focus"][0]["behind"] is True
    assert digest["wear"][0]["wear"] == "Кольцо"
    assert digest["top_cases"][0]["details"]["plan_percent"] == 12.0
    report = parse_llm_report(
        '{"headline":"Цены","situation":"Начните с цен.","notes":{"reprice":"Разрыв большой.","return":"","avoid":"Не возите Вывод.","playbook":"Позвоните A."}}'
    )
    assert report["headline"] == "Цены"
    assert report["notes"]["reprice"] == "Разрыв большой."
    assert report["notes"]["avoid"] == "Не возите Вывод."
    assert report["notes"]["playbook"] == "Позвоните A."
    assert "return" not in report["notes"]


def test_parse_llm_comments_items_key_and_text():
    raw = '{"items":[{"index":0,"text":"Сверить"}]}'
    assert parse_llm_comments(raw, 1) == ["Сверить"]
    wrapped = 'prefix {"comments":[{"index":0,"comment":"Ок"}]} suffix'
    assert parse_llm_comments(wrapped, 1) == ["Ок"]
    assert parse_llm_comments('{"comments":"bad"}', 1) == [None]
    assert parse_llm_comments('{"comments":[{"index":"x","comment":"A"}]}', 1) == ["A"]


def test_maybe_enrich_off_and_error(monkeypatch):
    report = RecommendationsResponse(generated_at=datetime.now(timezone.utc), items=[])
    monkeypatch.setattr(
        "app.services.llm_client.get_llm_config",
        lambda _db: _config(enabled=False),
    )
    out = maybe_enrich_recommendations(object(), report)
    assert out.llm_status == "off"

    monkeypatch.setattr(
        "app.services.llm_client.get_llm_config",
        lambda _db: _config(enabled=True, base_url=""),
    )
    out = maybe_enrich_recommendations(object(), report)
    assert out.llm_status == "error"


def test_parse_and_apply_matrix_cell_texts():
    raw = '{"cells":[{"index":1,"text":" Верните серьги "},{"index":0,"text":"Довезите кольца"}]}'
    texts = parse_llm_cell_texts(raw, 2)
    assert texts == ["Довезите кольца", "Верните серьги"]
    assert parse_llm_cell_texts("не json", 1) == [None]
    row = {"recommendations_text": "Верните 2 SKU"}
    apply_llm_cell_texts([row], ["Позвоните и заберите серьги"])
    assert row["recommendations_llm"] == "Позвоните и заберите серьги"
    assert row["recommendations_text"] == "Позвоните и заберите серьги"
    priced = {
        "recommendations_text": "Браслет −21% · BR-1 (−24%) · не выше 45 000 ₸",
    }
    apply_llm_cell_texts(
        [priced],
        ["Снизьте цену отгрузки для Браслет, чтобы соответствовать цене клиента."],
        [{"rules": [{"details": {"gap_percent": 21.4, "articles": [{"article": "BR-1"}]}}]}],
    )
    assert priced["recommendations_text"].startswith("Браслет −21%")
    assert cell_rules_have_facts([{"details": {"gap_percent": 21}}]) is True
    assert cell_rules_have_facts([{"title": "План"}]) is False


def test_collect_matrix_cells_prefers_score():
    weak = {
        "is_total": True,
        "recommendations": [{"title": "План", "score": 10}],
        "recommendations_text": "План",
    }
    strong = {
        "metal_color": {"dimension": "Красное 585"},
        "recommendations": [{"title": "Верните A", "score": 90, "action": "return"}],
        "recommendations_text": "Верните A",
    }
    payload, refs = collect_matrix_cell_payload(
        [{"counterparty": "ИП A", "matrix": [strong, weak]}],
        limit=1,
    )
    assert len(payload) == 1
    assert payload[0]["counterparty"] == "ИП A"
    assert payload[0]["dimensions"] == ["Красное 585"]
    assert refs[0] is strong
    messages = build_cell_enrich_messages(payload)
    assert "ячейку таблицы" in messages[0]["content"]
    assert "Цифры из rules обязательны" in messages[0]["content"]


def test_maybe_enrich_quarterly_applies_cell_text(monkeypatch):
    row = {"recommendations": [{"title": "Верните A", "score": 80}], "recommendations_text": "Верните A"}
    report = {"clients": [{"counterparty": "ИП A", "matrix": [row], "recommendations_text": "Верните A"}]}
    monkeypatch.setattr("app.services.llm_client.get_llm_config", lambda _db: _config())

    def fake_enrich(cells, _config, **_kwargs):
        assert cells[0]["counterparty"] == "ИП A"
        return ["Заберите кольца сегодня"], "ok"

    monkeypatch.setattr("app.services.llm_client.enrich_matrix_cells", fake_enrich)
    out = maybe_enrich_quarterly_summary(object(), report)
    assert out["llm_status"] == "ok"
    assert row["recommendations_text"] == "Заберите кольца сегодня"
    assert out["clients"][0]["recommendations_text"] == "Заберите кольца сегодня"


def test_maybe_enrich_quarterly_off(monkeypatch):
    report = {"clients": []}
    monkeypatch.setattr(
        "app.services.llm_client.get_llm_config",
        lambda _db: _config(enabled=False),
    )
    out = maybe_enrich_quarterly_summary(object(), report)
    assert out["llm_status"] == "off"
    assert out["llm_enabled"] is False


def test_settings_public_view_hides_key():
    row = SimpleNamespace(
        enabled=True,
        provider="openai_compatible",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key_encrypted="cipher",
        timeout_seconds=15,
        updated_at=None,
    )
    view = settings_public_view(row)
    assert view["api_key_set"] is True
    assert "api_key" not in view
    assert "cipher" not in view.values()
