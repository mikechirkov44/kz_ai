import httpx

from app.services.llm_settings import normalize_provider, provider_defaults
from app.services.openai_catalog import (
    fetch_openai_models,
    group_openai_models,
    is_chat_model,
    looks_like_openai,
    openai_model_groups,
)


def test_normalize_provider_from_legacy_and_url():
    assert normalize_provider("openai") == "openai"
    assert normalize_provider("openrouter") == "openrouter"
    assert normalize_provider("openai_compatible", "https://api.openai.com/v1") == "openai"
    assert normalize_provider("openai_compatible", "https://openrouter.ai/api/v1") == "openrouter"
    assert provider_defaults("openai")[1] == "gpt-6-astra"


def test_looks_like_openai():
    assert looks_like_openai("https://api.openai.com/v1")
    assert looks_like_openai("https://api.openai.com/v1/")
    assert not looks_like_openai("https://openrouter.ai/api/v1")
    assert not looks_like_openai("https://example.com/v1")


def test_is_chat_model_keeps_gpt_and_skips_embeddings():
    assert is_chat_model("gpt-6-astra")
    assert is_chat_model("gpt-4o-mini")
    assert is_chat_model("o3")
    assert not is_chat_model("text-embedding-3-large")
    assert not is_chat_model("whisper-1")
    assert not is_chat_model("dall-e-3")


def test_group_openai_models_puts_presets_first_and_keeps_live():
    groups = group_openai_models(
        [
            {"id": "text-embedding-3-small"},
            {"id": "gpt-4.1", "name": "GPT-4.1"},
            {"id": "gpt-6-astra"},
        ]
    )
    assert [group["id"] for group in groups] == ["openai"]
    ids = [item["id"] for item in groups[0]["models"]]
    assert ids[0] == "gpt-6-astra"
    assert "gpt-4o-mini" in ids
    assert "gpt-4.1" in ids
    assert "text-embedding-3-small" not in ids
    assert groups[0]["models"][0]["price_label"] == "по тарифу OpenAI"


def test_fetch_openai_models_empty_without_key_or_on_error():
    assert fetch_openai_models("") == []

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "no"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_openai_models("sk-test", client=client) == []


def test_openai_model_groups_uses_live_then_presets():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer sk-live"
        return httpx.Response(200, json={"data": [{"id": "gpt-4.1"}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    groups = openai_model_groups("sk-live", client=client)
    ids = [item["id"] for item in groups[0]["models"]]
    assert ids[0] == "gpt-6-astra"
    assert "gpt-4.1" in ids
