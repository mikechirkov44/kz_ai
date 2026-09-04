import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx

from app.domain.llm_enrich import (
    apply_llm_comments,
    build_enrich_messages,
    chat_completions_url,
    compact_recommendation_payload,
    parse_llm_comments,
    slice_for_enrichment,
)
from app.schemas import RecommendationItem, RecommendationsResponse
from app.services.llm_client import check_llm_connection, enrich_recommendation_items, maybe_enrich_recommendations
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
    assert json.loads(messages[1]["content"])[1]["message"] == "B"


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
    items, status = enrich_recommendation_items([], _config())
    assert items == []
    assert status == "ok"


def test_enrich_items_attaches_comments():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "gpt-4o-mini"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"comments":[{"index":0,"comment":"Обменять SKU"}]}'}}]},
        )

    items = [RecommendationItem(type="illiquid", severity="high", message="Вернуть артикул X")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status = enrich_recommendation_items(items, _config(), client=client)
    assert status == "ok"
    assert enriched[0].message == "Вернуть артикул X"
    assert enriched[0].llm_comment == "Обменять SKU"


def test_enrich_items_unparseable_content():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "просто текст"}}]})

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status = enrich_recommendation_items(items, _config(), client=client)
    assert status == "error"
    assert enriched[0].llm_comment is None


def test_enrich_items_empty_url():
    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    enriched, status = enrich_recommendation_items(items, _config(base_url=""))
    assert status == "error"
    assert enriched[0].message == "keep"


def test_enrich_items_fallback_on_bad_response():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status = enrich_recommendation_items(items, _config(), client=client)
    assert status == "error"
    assert enriched[0].llm_comment is None
    assert enriched[0].message == "keep"


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
