from __future__ import annotations

import httpx
import openai
import pytest

from llm.base import LLMError
from llm.factory import _DEFAULT_PROVIDERS, create_client, create_client_for_model, load_config
from llm.lmstudio_provider import DEFAULT_BASE_URL, LMStudioProvider, normalise_base_url
from llm.models import default_models_for, load_model_registry


@pytest.mark.parametrize(
    "given,expected",
    [
        (None, DEFAULT_BASE_URL),
        ("", DEFAULT_BASE_URL),
        ("   ", DEFAULT_BASE_URL),
        ("http://127.0.0.1:1234", "http://127.0.0.1:1234/v1"),
        ("http://127.0.0.1:1234/", "http://127.0.0.1:1234/v1"),
        ("http://127.0.0.1:1234/v1", "http://127.0.0.1:1234/v1"),
        ("http://192.168.1.5:1234/v1/", "http://192.168.1.5:1234/v1"),
    ],
)
def test_normalise_base_url(given, expected):
    assert normalise_base_url(given) == expected


def test_provider_identity_and_defaults():
    provider = LMStudioProvider()
    assert provider.get_provider() == "lmstudio"
    assert provider.get_base_url() == DEFAULT_BASE_URL


def test_provider_accepts_custom_base_url_without_api_key():
    provider = LMStudioProvider(base_url="http://localhost:4321")
    assert provider.get_base_url() == "http://localhost:4321/v1"


def test_registry_includes_lmstudio_tiers():
    registry = load_model_registry()
    assert set(registry["lmstudio"]) == {"low", "medium", "high"}
    assert all(registry["lmstudio"].values())


def test_default_models_for_returns_copy():
    defaults = default_models_for("lmstudio")
    defaults["low"] = "mutated"
    assert default_models_for("lmstudio")["low"] != "mutated"
    assert default_models_for("nope") == {}


def test_load_config_backfills_lmstudio_provider(tmp_path):
    legacy = tmp_path / "settings.json"
    legacy.write_text(
        '{"providers": {"anthropic": {"api_key": "", "default_model": "x"}},'
        ' "active_provider": "anthropic", "quiz_model": "x", "clean_model": "x"}'
    )
    config = load_config(legacy)
    assert config["providers"]["lmstudio"]["base_url"] == DEFAULT_BASE_URL


def test_factory_builds_lmstudio_client_with_base_url():
    config = {
        "active_provider": "lmstudio",
        "providers": {
            "lmstudio": {
                "api_key": "",
                "default_model": "some/model",
                "base_url": "http://localhost:9876",
            }
        },
    }
    client = create_client(config)
    assert isinstance(client, LMStudioProvider)
    assert client.get_base_url() == "http://localhost:9876/v1"


def test_factory_tolerates_lmstudio_config_without_base_url():
    config = {
        "active_provider": "lmstudio",
        "providers": {"lmstudio": {"api_key": "", "default_model": "some/model"}},
    }
    assert create_client(config).get_base_url() == DEFAULT_BASE_URL


def test_create_client_for_model_routes_registry_model_to_lmstudio():
    medium = load_model_registry()["lmstudio"]["medium"]
    config = {
        "active_provider": "anthropic",
        "providers": {**_DEFAULT_PROVIDERS},
    }
    client = create_client_for_model(config, medium)
    assert client.get_provider() == "lmstudio"


def test_complete_reports_unreachable_server_helpfully():
    provider = LMStudioProvider(base_url="http://127.0.0.1:9", default_model="anything")
    with pytest.raises(LLMError) as exc:
        provider.complete([{"role": "user", "content": "hi"}])
    assert "LM Studio" in str(exc.value)


def test_list_models_falls_back_to_registry_when_server_down():
    provider = LMStudioProvider(base_url="http://127.0.0.1:9")
    assert provider.list_models() == list(load_model_registry()["lmstudio"].values())


_HTTPX_RESPONSE = httpx.Response(400, request=httpx.Request("POST", "http://localhost:1234/v1"))


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content, finish_reason="stop"):
        self.message = _Message(content)
        self.finish_reason = finish_reason


class _Response:
    def __init__(self, content, finish_reason="stop"):
        self.choices = [_Choice(content, finish_reason)]


def _provider_returning(monkeypatch, content, finish_reason="stop"):
    provider = LMStudioProvider(default_model="test/model")
    monkeypatch.setattr(
        provider._client.chat.completions,
        "create",
        lambda **kwargs: _Response(content, finish_reason),
    )
    return provider


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("<think>weighing it up</think>\n\nAdrenaline 0.5 mg IM.", "Adrenaline 0.5 mg IM."),
        ("<thinking>hmm</thinking>Answer", "Answer"),
        ("<REASONING>x</REASONING> Answer ", "Answer"),
        ("  plain answer  ", "plain answer"),
    ],
)
def test_complete_strips_inline_reasoning(monkeypatch, raw, expected):
    provider = _provider_returning(monkeypatch, raw)
    assert provider.complete([{"role": "user", "content": "q"}]) == expected


def test_complete_errors_when_reasoning_consumes_the_token_budget(monkeypatch):
    provider = _provider_returning(monkeypatch, "", finish_reason="length")
    with pytest.raises(LLMError) as exc:
        provider.complete([{"role": "user", "content": "q"}])
    assert "reasoning" in str(exc.value).lower()


def test_complete_errors_on_empty_response(monkeypatch):
    provider = _provider_returning(monkeypatch, None)
    with pytest.raises(LLMError) as exc:
        provider.complete([{"role": "user", "content": "q"}])
    assert "empty response" in str(exc.value)


def test_complete_errors_when_only_reasoning_was_returned(monkeypatch):
    provider = _provider_returning(monkeypatch, "<think>all thought, no answer</think>")
    with pytest.raises(LLMError):
        provider.complete([{"role": "user", "content": "q"}])


def test_reasoning_effort_is_sent_by_default(monkeypatch):
    provider = LMStudioProvider(default_model="test/model")
    seen: dict = {}

    def fake_create(**kwargs):
        seen.update(kwargs)
        return _Response("answer")

    monkeypatch.setattr(provider._client.chat.completions, "create", fake_create)
    provider.complete([{"role": "user", "content": "q"}])
    assert seen["extra_body"] == {"reasoning_effort": "none"}


def test_reasoning_effort_can_be_overridden():
    provider = LMStudioProvider(default_model="test/model", reasoning_effort="High")
    assert provider._reasoning_effort == "high"


def test_reasoning_effort_omitted_when_blank(monkeypatch):
    provider = LMStudioProvider(default_model="test/model", reasoning_effort="")
    seen: dict = {}

    def fake_create(**kwargs):
        seen.update(kwargs)
        return _Response("answer")

    monkeypatch.setattr(provider._client.chat.completions, "create", fake_create)
    provider.complete([{"role": "user", "content": "q"}])
    assert "extra_body" not in seen


def test_server_rejecting_reasoning_effort_falls_back_and_stops_resending(monkeypatch):
    provider = LMStudioProvider(default_model="test/model")
    calls: list[bool] = []

    def fake_create(**kwargs):
        has_extra = "extra_body" in kwargs
        calls.append(has_extra)
        if has_extra:
            raise openai.BadRequestError(
                "unknown parameter", response=_HTTPX_RESPONSE, body=None
            )
        return _Response("answer")

    monkeypatch.setattr(provider._client.chat.completions, "create", fake_create)

    assert provider.complete([{"role": "user", "content": "q"}]) == "answer"
    # Second call must not retry the rejected parameter.
    assert provider.complete([{"role": "user", "content": "q"}]) == "answer"
    assert calls == [True, False, False]


_SCHEMA = {"type": "object", "properties": {"score": {"type": "string"}}}


def _capture(monkeypatch, provider):
    seen: dict = {}

    def fake_create(**kwargs):
        seen.update(kwargs)
        return _Response('{"score": "correct"}')

    monkeypatch.setattr(provider._client.chat.completions, "create", fake_create)
    return seen


def test_schema_is_applied_to_models_that_need_it(monkeypatch):
    provider = LMStudioProvider(default_model="medgemma-1.5-4b-it")
    seen = _capture(monkeypatch, provider)
    provider.complete([{"role": "user", "content": "q"}], response_schema=_SCHEMA)
    fmt = seen["extra_body"]["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["schema"] == _SCHEMA


def test_schema_is_withheld_from_models_it_would_degrade(monkeypatch):
    provider = LMStudioProvider(default_model="openai/gpt-oss-20b")
    seen = _capture(monkeypatch, provider)
    provider.complete([{"role": "user", "content": "q"}], response_schema=_SCHEMA)
    assert "response_format" not in seen["extra_body"]


def test_schema_follows_the_per_call_model_override(monkeypatch):
    provider = LMStudioProvider(default_model="openai/gpt-oss-20b")
    seen = _capture(monkeypatch, provider)
    provider.complete(
        [{"role": "user", "content": "q"}],
        model="medgemma-1.5-4b-it",
        response_schema=_SCHEMA,
    )
    assert "response_format" in seen["extra_body"]


def test_no_schema_offered_means_none_sent(monkeypatch):
    provider = LMStudioProvider(default_model="medgemma-1.5-4b-it")
    seen = _capture(monkeypatch, provider)
    provider.complete([{"role": "user", "content": "q"}])
    assert "response_format" not in seen["extra_body"]


def test_get_model_reports_the_default(monkeypatch):
    assert LMStudioProvider(default_model="a/b").get_model() == "a/b"
