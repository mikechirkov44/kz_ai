import httpx

from app.services.openrouter_catalog import (
    classify_tier,
    fetch_openrouter_models,
    group_openrouter_models,
    looks_like_openrouter,
)


def test_classify_tier_free_cheap_premium():
    assert classify_tier("meta-llama/llama-3.3-70b-instruct:free", 0.0, 0.0) == "free"
    assert classify_tier("openrouter/free", 1.0, 1.0) == "free"
    assert classify_tier("openai/gpt-4o-mini", 0.15, 0.6) == "cheap"
    assert classify_tier("anthropic/claude-3.5-sonnet", 3.0, 15.0) == "premium"


def test_group_openrouter_models_skips_variants_and_limits():
    rows = [
        {
            "id": "meta-llama/llama-3.1-8b-instruct:free",
            "name": "Llama 8B",
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {"id": "openrouter/free", "name": "Free router", "pricing": {"prompt": "0", "completion": "0"}},
        {
            "id": "openai/gpt-4o-mini",
            "name": "GPT-4o mini",
            "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
        },
        {
            "id": "anthropic/claude-3.5-sonnet",
            "name": "Sonnet",
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
        },
        {"id": "google/gemini-flash:nitro", "name": "Nitro", "pricing": {"prompt": "0", "completion": "0"}},
        {"id": "openai/gpt-4o-mini", "name": "dup"},
    ]
    groups = group_openrouter_models(rows, limit=2)
    by_id = {group["id"]: group for group in groups}
    assert [group["id"] for group in groups] == ["free", "cheap", "premium"]
    assert [item["id"] for item in by_id["free"]["models"]] == [
        "meta-llama/llama-3.1-8b-instruct:free",
        "openrouter/free",
    ]
    assert by_id["free"]["models"][0]["price_label"] == "бесплатно"
    assert by_id["cheap"]["models"][0]["id"] == "openai/gpt-4o-mini"
    assert by_id["premium"]["models"][0]["id"] == "anthropic/claude-3.5-sonnet"


def test_fetch_openrouter_models_empty_on_http_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="down")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_openrouter_models(client=client) == []


def test_fetch_openrouter_models_reads_data():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/api/v1/models")
        return httpx.Response(200, json={"data": [{"id": "openrouter/free"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_openrouter_models(client=client) == [{"id": "openrouter/free"}]


def test_looks_like_openrouter():
    assert looks_like_openrouter("https://openrouter.ai/api/v1")
    assert looks_like_openrouter("https://openrouter.ai/api/v1/")
    assert not looks_like_openrouter("https://api.openai.com/v1")
