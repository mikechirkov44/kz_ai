import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx

from app.domain.llm_enrich import (
    COMMENT_BATCH_SIZE,
    MATRIX_BATCH_SIZE,
    advice_is_useful,
    apply_llm_cell_texts,
    apply_llm_comments,
    build_cell_enrich_messages,
    build_comment_enrich_messages,
    build_enrich_messages,
    build_llm_digest,
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
    MAX_COMPLETION_TOKENS,
    _http_error_message,
    affordable_max_tokens,
    check_llm_connection,
    comment_max_tokens,
    enrich_matrix_cells,
    enrich_recommendation_items,
    enrich_timeout,
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


def test_parse_salvages_truncated_json():
    truncated_cells = (
        '{"cells":[{"index":0,"text":"Сначала заберите кольца сегодня"},'
        '{"index":1,"text":"На звонке скажите'
    )
    assert parse_llm_cell_texts(truncated_cells, 2)[0] == "Сначала заберите кольца сегодня"
    assert parse_llm_cell_texts(truncated_cells, 2)[1] is None
    truncated_comments = (
        '{"comments":[{"index":0,"comment":"Обменять SKU"},{"index":1,"comment":"обрыв'
    )
    assert parse_llm_comments(truncated_comments, 2)[0] == "Обменять SKU"
    assert parse_llm_comments(truncated_comments, 2)[1] is None
    plain = "Сначала заберите кольца сегодня. · На звонке назовите потолок и не обещайте новое."
    assert parse_llm_cell_texts(plain, 1) == [plain]
    cut = '{"comments":[{"index":0,"comment":"Сначала заберите кольца сегодня'
    assert parse_llm_cell_texts(cut, 1)[0] == "Сначала заберите кольца сегодня"


def test_enrich_timeout_floor():
    assert enrich_timeout(_config(timeout_seconds=10)) == 60
    assert enrich_timeout(_config(timeout_seconds=90)) == 90


def test_openrouter_credit_token_cap():
    assert comment_max_tokens(8) == MAX_COMPLETION_TOKENS
    assert comment_max_tokens(1, 250) == 250
    assert affordable_max_tokens(
        "You requested up to 1320 tokens, but can only afford 446.",
        1320,
    ) == 446
    assert affordable_max_tokens(
        "You requested up to 400 tokens, but can only afford 446.",
        400,
    ) is None
    assert affordable_max_tokens("boom", 400) is None
    unpaid = (
        '{"error":{"message":"Insufficient credits. This account never purchased credits. '
        'Make sure your key is on the correct account or org, and if so, purchase more at '
        'https://openrouter.ai/settings/credits","code":402}}'
    )
    paid = _http_error_message(402, unpaid, model="gpt-4o-mini")
    assert ":free" in paid
    assert "платная" in paid
    assert "openrouter.ai/settings/credits" in paid
    assert "never purchased" not in paid.lower()
    free = _http_error_message(402, unpaid, model="meta-llama/llama-3.3-70b-instruct:free")
    assert "предоплаченных" in free
    assert "Кредитная линия" in free
    assert "never purchased" not in free.lower()


def test_enrich_retries_openrouter_402():
    tokens: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        tokens.append(int(body["max_tokens"]))
        user = json.loads(body["messages"][1]["content"])
        if int(body["max_tokens"]) > 200:
            return httpx.Response(
                402,
                text='{"error":{"message":"You requested up to 400 tokens, but can only afford 180."}}',
            )
        if "items" in user:
            content = '{"comments":[{"index":0,"comment":"Заберите сегодня"}]}'
        else:
            content = '{"headline":"Сначала возврат","situation":"Позвоните A."}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status, summary, report, error = enrich_recommendation_items(items, _config(), client=client)
    assert status == "ok"
    assert error is None
    assert 400 in tokens
    assert 180 in tokens
    assert all(value <= MAX_COMPLETION_TOKENS for value in tokens)
    assert enriched[0].llm_comment == "Заберите сегодня"
    assert summary == "Сначала возврат"
    assert report and report["headline"] == "Сначала возврат"


def test_advice_style_does_not_change_token_budget():
    tokens: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        tokens.append(int(body["max_tokens"]))
        user = json.loads(body["messages"][1]["content"])
        if "items" in user:
            content = '{"comments":[{"index":0,"comment":"Заберите сегодня"}]}'
        else:
            content = '{"headline":"Сначала возврат","situation":"Позвоните A."}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    _enriched, status, _summary, _report, error = enrich_recommendation_items(
        items, _config(advice_style="economy"), client=client
    )
    assert status == "ok"
    assert error is None
    assert tokens
    assert all(value == MAX_COMPLETION_TOKENS for value in tokens)


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
    assert "items" not in user
    assert user["digest"]["total"] == 2
    assert "playbook" in user["digest"]
    comment_user = json.loads(build_comment_enrich_messages(items)[1]["content"])
    assert comment_user["items"][1]["message"] == "B"
    assert "до 120 знаков" in build_comment_enrich_messages(items, style="economy")[0]["content"]
    assert "до 320 знаков" in build_comment_enrich_messages(items, style="detailed")[0]["content"]
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


def test_llm_test_connection_openrouter_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["HTTP-Referer"] == "https://github.com/mikechirkov44/kz_ai"
        assert request.headers["X-Title"] == "AI Jewelry Analytics"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = check_llm_connection(
        _config(base_url="https://openrouter.ai/api/v1", model="openrouter/free"),
        client=client,
    )
    assert result["status"] == "ok"


def test_llm_test_connection_http_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = check_llm_connection(_config(), client=client)
    assert result["status"] == "error"
    assert "unauthorized" in result["detail"]


def test_llm_test_connection_openrouter_unpaid():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            402,
            text='{"error":{"message":"This account never purchased credits","code":402}}',
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = check_llm_connection(_config(), client=client)
    assert result["status"] == "error"
    assert ":free" in result["detail"]
    free = check_llm_connection(_config(model="openrouter/free"), client=client)
    assert free["status"] == "error"
    assert "предоплаченных" in free["detail"]


def test_enrich_openrouter_never_purchased():
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            402,
            text='{"error":{"message":"Insufficient credits. This account never purchased credits."}}',
        )

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    _enriched, status, _summary, _report, error = enrich_recommendation_items(items, _config(), client=client)
    assert status == "error"
    assert error and ":free" in error
    assert calls["n"] == 2


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
    items, status, summary, report, error = enrich_recommendation_items([], _config())
    assert items == []
    assert status == "ok"
    assert summary is None
    assert report is None
    assert error is None


def test_enrich_items_attaches_comments():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "gpt-4o-mini"
        user = json.loads(body["messages"][1]["content"])
        if "items" in user:
            content = '{"comments":[{"index":0,"comment":"Обменять SKU"}]}'
        else:
            content = '{"summary":"Начните с возврата.","headline":"Начните с возврата.","situation":"Начните с возврата."}'
        assert body["max_tokens"] <= MAX_COMPLETION_TOKENS
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    items = [RecommendationItem(type="illiquid", severity="high", message="Вернуть артикул X")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status, summary, report, error = enrich_recommendation_items(items, _config(), client=client)
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
    enriched, status, summary, report, error = enrich_recommendation_items(items, _config(), client=client)
    assert status == "error"
    assert enriched[0].llm_comment is None
    assert summary is None
    assert report is None


def test_enrich_items_empty_url():
    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    enriched, status, summary, report, error = enrich_recommendation_items(items, _config(base_url=""))
    assert status == "error"
    assert enriched[0].message == "keep"
    assert summary is None
    assert report is None


def test_enrich_items_fallback_on_bad_response():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status, summary, report, error = enrich_recommendation_items(items, _config(), client=client)
    assert status == "error"
    assert enriched[0].llm_comment is None
    assert enriched[0].message == "keep"
    assert summary is None
    assert report is None


def test_enrich_items_report_ok_without_comments():
    def handler(request: httpx.Request) -> httpx.Response:
        user = json.loads(json.loads(request.content.decode("utf-8"))["messages"][1]["content"])
        if "items" in user:
            return httpx.Response(200, json={"choices": [{"message": {"content": "не json"}}]})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"headline":"Сначала возврат","situation":"Позвоните A."}'}}]},
        )

    items = [RecommendationItem(type="illiquid", severity="high", message="keep")]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status, summary, report, error = enrich_recommendation_items(items, _config(), client=client)
    assert status == "ok"
    assert enriched[0].llm_comment is None
    assert summary == "Сначала возврат"
    assert report and report["headline"] == "Сначала возврат"


def test_enrich_items_comment_batches_keep_partial():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        user = json.loads(json.loads(request.content.decode("utf-8"))["messages"][1]["content"])
        if "items" not in user:
            return httpx.Response(500, text="report-fail")
        if calls["n"] == 2:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"comments":[{"index":0,"comment":"Заберите сегодня"}]}'}}]},
            )
        return httpx.Response(500, text="later-fail")

    items = [
        RecommendationItem(type="illiquid", severity="high", message=f"item-{i}")
        for i in range(COMMENT_BATCH_SIZE + 1)
    ]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    enriched, status, summary, report, error = enrich_recommendation_items(items, _config(), client=client)
    assert status == "ok"
    assert calls["n"] == 3
    assert enriched[0].llm_comment == "Заберите сегодня"
    assert enriched[-1].llm_comment is None
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
    assert out.llm_error == "crash"
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
        return items, "ok", "Сводка модели", {"headline": "Сводка", "situation": "Сводка модели", "notes": {}}, None

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
    assert out.llm_error == "Не указан адрес API модели"


def test_parse_and_apply_matrix_cell_texts():
    raw = '{"cells":[{"index":1,"text":" Верните серьги "},{"index":0,"text":"Довезите кольца"}]}'
    texts = parse_llm_cell_texts(raw, 2)
    assert texts == ["Довезите кольца", "Верните серьги"]
    assert parse_llm_cell_texts('{"cells":[{"index":0,"advice":"Сначала заберите кольца"}]}', 1) == [
        "Сначала заберите кольца"
    ]
    assert parse_llm_cell_texts('{"cells":[{"index":0,"tip":"На звонке назовите потолок"}]}', 1) == [
        "На звонке назовите потолок"
    ]
    assert parse_llm_cell_texts('{"cells":[{"index":0,"совет":"Не везите новое, пока не заберут."}]}', 1) == [
        "Не везите новое, пока не заберут."
    ]
    assert parse_llm_cell_texts(
        '{"comments":[{"index":0,"comment":"На этой неделе заберите кольца. · На звонке не обещайте новое."}]}',
        1,
    ) == ["На этой неделе заберите кольца. · На звонке не обещайте новое."]
    assert parse_llm_cell_texts("1. Сначала заберите серьги сегодня.\n2. На звонке назовите потолок.", 2) == [
        "Сначала заберите серьги сегодня.",
        "На звонке назовите потолок.",
    ]
    row = {"recommendations_text": "Верните 2 SKU"}
    brief = (
        "На этой неделе сначала заберите серьги с витрины. · "
        "На звонке скажите, что новое не везём. · "
        "Если клиент просит кольца — не обещайте отгрузку сегодня."
    )
    apply_llm_cell_texts([row], [brief])
    assert row["recommendations_llm"] == brief
    assert row["recommendations_text"] == "Верните 2 SKU"
    priced = {
        "recommendations_text": "Клиент продаёт «Браслет» на 21% дешевле отгрузки. Следующие отгрузки — не выше 45 000 ₸.",
    }
    apply_llm_cell_texts(
        [priced],
        ["Клиент продаёт браслет на 21% дешевле отгрузки, следующие отгрузки не выше 45 000."],
        [{"facts": priced["recommendations_text"]}],
    )
    assert "recommendations_llm" not in priced
    assert advice_is_useful(
        "На этой неделе не раздувайте отгрузку. · Сначала заберите К0237 и назовите потолок 45 000 ₸. · "
        "Если клиент просит новое — не обещайте, пока не заберут.",
        priced["recommendations_text"],
    )
    assert not advice_is_useful(
        f"{priced['recommendations_text']} Сначала заберите К0237, новые не везите.",
        priced["recommendations_text"],
    )
    assert not advice_is_useful(
        "Клиент продаёт «Браслет» на 21% дешевле отгрузки. Следующие отгрузки — не выше 45 000 ₸.",
        priced["recommendations_text"],
    )


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
        [{"counterparty": "ИП A", "work_type_label": "Рост", "shipment_percent": 40, "matrix": [strong, weak]}],
        limit=1,
    )
    assert len(payload) == 1
    assert payload[0]["counterparty"] == "ИП A"
    assert payload[0]["dimensions"] == ["Красное 585"]
    assert payload[0]["work_type"] == "Рост"
    assert payload[0]["plan_percent"] == 40
    assert payload[0]["facts"] == "Верните A"
    assert "message" not in payload[0]["rules"][0]
    assert payload[0]["rules"][0]["title"] == "Верните A"
    assert refs[0] is strong
    messages = build_cell_enrich_messages(payload)
    assert "3 пункта" in messages[0]["content"]
    assert '{"comments"' in messages[0]["content"]
    assert "items" in json.loads(messages[1]["content"])
    from decimal import Decimal

    decimal_messages = build_cell_enrich_messages([{"plan_percent": Decimal("12.5"), "facts": "A"}])
    assert "12.5" in decimal_messages[1]["content"]


def _chat_response(content: str, status: int = 200) -> httpx.Response:
    if status >= 400:
        return httpx.Response(status, text=content)
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_enrich_matrix_cells_batches_keep_partial():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.loads(request.content)
        user = json.loads(body["messages"][1]["content"])
        assert len(user["items"]) <= MATRIX_BATCH_SIZE
        if calls["n"] == 1:
            return _chat_response('{"comments":[{"index":0,"comment":"Сначала заберите кольца сегодня"}]}')
        return _chat_response("fail", status=500)

    cells = [{"facts": f"cell-{i}", "index": i} for i in range(MATRIX_BATCH_SIZE + 1)]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    texts, status, error = enrich_matrix_cells(cells, _config(), client=client)
    assert status == "ok"
    assert not error
    assert calls["n"] == 2
    assert texts[0] == "Сначала заберите кольца сегодня"
    assert texts[-1] is None


def test_enrich_matrix_cells_plain_paragraph():
    def handler(_: httpx.Request) -> httpx.Response:
        return _chat_response(
            "Сначала заберите кольца сегодня. · На звонке назовите потолок. · Если просят новое — не обещайте."
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    texts, status, error = enrich_matrix_cells([{"facts": "Верните A"}], _config(), client=client)
    assert status == "ok"
    assert not error
    assert texts[0].startswith("Сначала заберите кольца")


def test_enrich_matrix_cells_all_failed():
    def handler(_: httpx.Request) -> httpx.Response:
        return _chat_response("not-json")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    texts, status, error = enrich_matrix_cells([{"facts": "A"}], _config(), client=client)
    assert status == "error"
    assert error
    assert texts == [None]


def test_maybe_enrich_quarterly_applies_cell_text(monkeypatch):
    row = {"recommendations": [{"title": "Верните A", "score": 80}], "recommendations_text": "Верните A"}
    report = {"clients": [{"counterparty": "ИП A", "matrix": [row], "recommendations_text": "Верните A"}]}
    monkeypatch.setattr("app.services.llm_client.get_llm_config", lambda _db: _config())

    def fake_enrich(cells, _config, **_kwargs):
        assert cells[0]["counterparty"] == "ИП A"
        return [
            "На этой неделе заберите кольца с полки. · На звонке не обещайте новое. · Если клиент просит довоз — сначала возврат."
        ], "ok", ""

    monkeypatch.setattr("app.services.llm_client.enrich_matrix_cells", fake_enrich)
    out = maybe_enrich_quarterly_summary(object(), report)
    assert out["llm_status"] == "ok"
    assert row["recommendations_text"] == "Верните A"
    assert row["recommendations_llm"].startswith("На этой неделе заберите кольца")
    assert out["clients"][0]["recommendations_llm"].startswith("На этой неделе заберите кольца")


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
    assert view["advice_style"] == "standard"
    assert settings_public_view(SimpleNamespace(**{**row.__dict__, "advice_style": "detailed"}))["advice_style"] == "detailed"
    assert "api_key" not in view
    assert "cipher" not in view.values()
