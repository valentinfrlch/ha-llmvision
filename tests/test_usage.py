"""Accounting contracts: actual counts, bounded metadata and durable HA totals."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.llmvision import ServiceCallData
from custom_components.llmvision.providers import OpenAI, AWSBedrock, Request
from custom_components.llmvision.usage import (
    EVENT_TOKEN_USAGE,
    EVENT_CALL_FINISHED,
    USAGE_DATA,
    UsageManager,
    async_get_manager,
    normalize_usage,
    safe_model,
)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            {
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                    "prompt_tokens_details": {"cached_tokens": 60},
                    "completion_tokens_details": {"reasoning_tokens": 8},
                }
            },
            {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
                "cache_read_tokens": 60,
                "reasoning_tokens": 8,
            },
        ),
        (
            {
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "cache_read_input_tokens": 70,
                    "cache_creation_input_tokens": 30,
                }
            },
            {
                "input_tokens": 110,
                "output_tokens": 20,
                "total_tokens": 130,
                "cache_read_tokens": 70,
                "cache_write_tokens": 30,
            },
        ),
        (
            {
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 20,
                    "thoughtsTokenCount": 30,
                    "cachedContentTokenCount": 50,
                    "totalTokenCount": 150,
                }
            },
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "cache_read_tokens": 50,
                "reasoning_tokens": 30,
            },
        ),
        (
            {
                "usage": {
                    "inputTokens": 10,
                    "outputTokens": 5,
                    "cacheReadInputTokens": 30,
                    "cacheWriteInputTokens": 20,
                    "totalTokens": 15,
                }
            },
            {
                "input_tokens": 60,
                "output_tokens": 5,
                "total_tokens": 65,
                "cache_read_tokens": 30,
                "cache_write_tokens": 20,
            },
        ),
        (
            {"prompt_eval_count": 42, "eval_count": 7},
            {"input_tokens": 42, "output_tokens": 7, "total_tokens": 49},
        ),
        (
            {"usage": {"prompt_tokens": 0, "completion_tokens": 0}},
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        ),
    ],
)
def test_normalize_provider_shapes(response, expected):
    assert normalize_usage(response) == expected


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {},
        {"usage": None},
        {"usage": []},
        {"usage": {"total_tokens": 10}},
        {"usage": {"prompt_tokens": 5}},
        {"usage": {"prompt_tokens": True, "completion_tokens": 5}},
        {"usage": {"prompt_tokens": -1, "completion_tokens": 5}},
        {"usage": {"prompt_tokens": "5", "completion_tokens": 5}},
        {"usage": {"prompt_tokens": 1.2, "completion_tokens": 5}},
        {
            "usage": {
                "input_tokens": 5,
                "output_tokens": 1,
                "cache_read_input_tokens": "bad",
            }
        },
        {
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 1,
                "thoughtsTokenCount": None,
            }
        },
    ],
)
def test_unknown_or_malformed_usage_never_becomes_zero(response):
    assert normalize_usage(response) is None


def test_invalid_optional_subsets_not_added():
    assert normalize_usage(
        {
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "prompt_tokens_details": {"cached_tokens": 99},
                "completion_tokens_details": [],
            }
        }
    ) == {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}


@pytest.mark.parametrize(
    "model",
    [
        "https://example.com/key",
        "secret prompt\ncontent",
        "x" * 129,
        None,
        {"secret": "key"},
    ],
)
def test_model_text_is_bounded(model):
    assert safe_model(model) is None


def test_normal_model_identifiers():
    assert safe_model("org/model:latest") == "org/model:latest"


@pytest.fixture
def enabled_hass(hass):
    settings = MockConfigEntry(
        domain="llmvision", data={"provider": "Settings", "track_usage": True}
    )
    settings.add_to_hass(hass)
    hass.data["llmvision"] = {"provider-id": {"provider": "OpenAI"}}
    return hass


def record_args(**overrides):
    return dict(
        entry_id="provider-id",
        provider="OpenAI",
        model="gpt-test",
        service="image_analyzer",
        phase="analysis",
        usage={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        failed=False,
        duration_ms=1,
        **overrides
    )


async def test_persistence_concurrency_toggle_and_privacy(enabled_hass, hass_storage):
    hass = enabled_hass
    manager = await async_get_manager(hass)
    events = []
    hass.bus.async_listen(EVENT_TOKEN_USAGE, events.append)
    context = Context()
    await asyncio.gather(
        *(manager.async_record(**record_args(context=context)) for _ in range(5))
    )
    await hass.async_block_till_done()
    assert manager.get_totals("provider-id")["calls"] == 5
    assert manager.get_totals("provider-id")["total_tokens"] == 60
    assert len(events) == 5
    assert all(event.context is context for event in events)
    assert set(events[0].data) == {
        "schema",
        "provider",
        "config_entry_id",
        "model",
        "service",
        "request_type",
        "status",
        "usage_available",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    }
    # An independent manager performs a real HA Store load, not a sensor copy.
    restored = UsageManager(hass)
    await restored.async_load()
    assert restored.get_totals("provider-id") == manager.get_totals("provider-id")
    assert set(hass_storage[USAGE_DATA]["data"]) == {"provider-id"}
    manager.set_enabled(False)
    await manager.async_record(**record_args())
    assert manager.get_totals("provider-id")["calls"] == 5
    manager.set_enabled(True)
    await manager.async_record(**record_args())
    assert manager.get_totals("provider-id")["calls"] == 6
    await manager.async_remove("provider-id")
    assert manager.get_totals("provider-id")["calls"] == 0


async def test_missing_usage_and_failure_not_fabricated(enabled_hass):
    manager = await async_get_manager(enabled_hass)
    events, finished = [], []
    enabled_hass.bus.async_listen(EVENT_TOKEN_USAGE, events.append)
    enabled_hass.bus.async_listen(EVENT_CALL_FINISHED, finished.append)
    args = record_args()
    args.update(
        usage=None, failed=True, service="private payload", model="https://secret"
    )
    await manager.async_record(**args)
    await enabled_hass.async_block_till_done()
    assert not events
    assert len(finished) == 1
    assert finished[0].data["service"] == "unknown"
    assert "model" not in finished[0].data
    totals = manager.get_totals("provider-id")
    assert (
        totals["calls"],
        totals["errors"],
        totals["missing_usage"],
        totals["total_tokens"],
    ) == (1, 1, 1, 0)


async def test_persistence_failure_never_fails_analysis(enabled_hass):
    manager = await async_get_manager(enabled_hass)
    with patch.object(manager._store, "async_save", side_effect=OSError("SECRET")):
        await manager.async_record(**record_args())
    assert manager.get_totals("provider-id")["calls"] == 1


def make_call():
    return SimpleNamespace(
        provider="provider-id",
        model="test-model",
        message="PRIVATE PROMPT",
        max_tokens=32,
        context=Context(),
        service="image_analyzer",
    )


def response(usage=True, content="text", finish_reason="stop"):
    result = {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "id": "PRIVATE-RESPONSE-ID",
        "model": "PRIVATE-MODEL-RESPONSE",
    }
    if usage:
        result["usage"] = {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
        }
    return Mock(status=200, json=AsyncMock(return_value=result))


async def test_analysis_and_title_are_distinct_actual_calls(enabled_hass):
    manager = await async_get_manager(enabled_hass)
    session = SimpleNamespace(post=AsyncMock(side_effect=[response(), response()]))
    with patch(
        "custom_components.llmvision.providers.async_get_clientsession",
        return_value=session,
    ):
        provider = OpenAI(enabled_hass, "PRIVATE-KEY", "test-model")
    provider._prepare_vision_data = Mock(return_value={"messages": "PRIVATE"})
    provider._prepare_text_data = Mock(return_value={"messages": "PRIVATE TITLE"})
    call = make_call()
    assert await provider.vision_request(call) == "text"
    assert await provider.title_request(call) == "text"
    totals = manager.get_totals(call.provider)
    assert session.post.await_count == 2
    assert totals["calls"] == 2
    assert totals["analysis_total_tokens"] == totals["title_total_tokens"] == 12
    assert totals["total_tokens"] == 24


async def test_disabled_no_accounting_and_no_payload_changes(enabled_hass):
    manager = await async_get_manager(enabled_hass)
    manager.set_enabled(False)
    session = SimpleNamespace(post=AsyncMock(return_value=response()))
    with patch(
        "custom_components.llmvision.providers.async_get_clientsession",
        return_value=session,
    ):
        provider = OpenAI(enabled_hass, "key", "test-model")
    payload = {"messages": "original"}
    provider._prepare_vision_data = Mock(return_value=payload)
    assert await provider.vision_request(make_call()) == "text"
    assert session.post.await_count == 1
    assert session.post.call_args.kwargs["json"] is payload
    assert manager.get_totals("provider-id")["calls"] == 0


@pytest.mark.parametrize("kind", ["http", "json", "network", "invalid", "missing"])
async def test_failures_preserve_actual_usage(enabled_hass, kind):
    manager = await async_get_manager(enabled_hass)
    reply = response(usage=kind != "missing")
    if kind == "invalid":
        # The upstream adapter rejects an empty choices list after the usage
        # envelope has been captured. Accounting must retain those counts even
        # though response parsing fails, without adding new validation policy.
        result = await reply.json()
        result["choices"] = []
    if kind == "http":
        reply.status = 429
    if kind == "json":
        reply.json.side_effect = ValueError("SECRET")
    session = SimpleNamespace(post=AsyncMock(return_value=reply))
    if kind == "network":
        session.post.side_effect = TimeoutError("SECRET")
    with patch(
        "custom_components.llmvision.providers.async_get_clientsession",
        return_value=session,
    ):
        provider = OpenAI(enabled_hass, "key", "test-model")
    provider._prepare_vision_data = Mock(return_value={})
    if kind == "missing":
        assert await provider.vision_request(make_call()) == "text"
    else:
        with pytest.raises(ServiceValidationError):
            await provider.vision_request(make_call())
    totals = manager.get_totals("provider-id")
    assert totals["calls"] == 1
    assert totals["errors"] == int(kind != "missing")
    assert totals["total_tokens"] == (12 if kind == "invalid" else 0)
    assert totals["missing_usage"] == int(kind != "invalid")


@pytest.mark.parametrize(
    ("content", "finish_reason"), [("", "stop"), ("text", "length")]
)
async def test_usage_preserves_existing_response_validation(
    enabled_hass, content, finish_reason
):
    """Accounting does not introduce stricter OpenAI response acceptance rules."""
    manager = await async_get_manager(enabled_hass)
    session = SimpleNamespace(
        post=AsyncMock(
            return_value=response(content=content, finish_reason=finish_reason)
        )
    )
    with patch(
        "custom_components.llmvision.providers.async_get_clientsession",
        return_value=session,
    ):
        provider = OpenAI(enabled_hass, "key", "test-model")
    provider._prepare_vision_data = Mock(return_value={})
    assert await provider.vision_request(make_call()) == content
    totals = manager.get_totals("provider-id")
    assert totals["calls"] == 1
    assert totals["errors"] == 0
    assert totals["total_tokens"] == 12
    assert totals["missing_usage"] == 0


async def test_preparation_failure_does_not_count_an_api_call(enabled_hass):
    manager = await async_get_manager(enabled_hass)
    with patch("custom_components.llmvision.providers.async_get_clientsession"):
        provider = OpenAI(enabled_hass, "key", "test-model")
    provider._prepare_vision_data = Mock(side_effect=ValueError("bad config"))
    with pytest.raises(ValueError):
        await provider.vision_request(make_call())
    assert manager.get_totals("provider-id")["calls"] == 0


async def test_validation_excluded_without_extra_calls(enabled_hass):
    manager = await async_get_manager(enabled_hass)
    session = SimpleNamespace(post=AsyncMock(return_value=response()))
    with patch(
        "custom_components.llmvision.providers.async_get_clientsession",
        return_value=session,
    ):
        provider = OpenAI(enabled_hass, "key", "test-model")
    await provider.validate()
    assert session.post.await_count == 1
    assert manager.get_totals("provider-id")["calls"] == 0


async def test_storage_load_failure_disables_tracking_without_overwrite(enabled_hass):
    manager = UsageManager(enabled_hass)
    with patch.object(
        manager._store, "async_load", side_effect=OSError("SECRET")
    ), patch.object(manager._store, "async_save", new_callable=AsyncMock) as save:
        await manager.async_load()
        manager.set_enabled(True)
        assert not manager.enabled
        await manager.async_record(**record_args())
        save.assert_not_awaited()


async def test_removed_provider_cannot_be_recreated_by_inflight_call(enabled_hass):
    manager = await async_get_manager(enabled_hass)
    await manager.async_record(**record_args())
    await manager.async_remove("provider-id")
    await manager.async_record(**record_args())
    assert manager.get_totals("provider-id")["calls"] == 0


async def test_settings_unload_disables_only_after_success(enabled_hass):
    from custom_components.llmvision import async_setup_entry, async_unload_entry

    hass = enabled_hass
    manager = await async_get_manager(hass)
    settings = hass.config_entries.async_entries("llmvision")[0]
    with patch.object(
        hass.config_entries, "async_unload_platforms", new_callable=AsyncMock
    ) as unload:
        unload.return_value = False
        assert not await async_unload_entry(hass, settings)
        assert manager.enabled
        unload.return_value = True
        assert await async_unload_entry(hass, settings)
        assert not manager.enabled
    with patch.object(
        hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
    ), patch("custom_components.llmvision.Timeline") as timeline:
        timeline.return_value._cleanup = AsyncMock()
        await async_setup_entry(hass, settings)
    assert manager.enabled


async def test_canonical_openwebui_is_accounted(enabled_hass):
    from custom_components.llmvision.usage import is_provider_entry

    assert is_provider_entry(SimpleNamespace(data={"provider": "OpenWebUI"}))
    manager = await async_get_manager(enabled_hass)
    args = record_args()
    args["provider"] = "OpenWebUI"
    await manager.async_record(**args)
    assert manager.get_totals("provider-id")["calls"] == 1


async def test_service_attribution_preserves_context():
    # Real HA calls expose these outside .data; no service payload is copied.
    context = Context()
    call = ServiceCallData(
        SimpleNamespace(data={}, context=context, service="stream_analyzer")
    )
    assert call.context is context
    assert call.service == "stream_analyzer"


async def test_manager_first_load_is_shared_and_serialized(enabled_hass):
    managers = await asyncio.gather(
        *(async_get_manager(enabled_hass) for _ in range(10))
    )
    assert all(manager is managers[0] for manager in managers)


async def test_real_provider_platform_setup_reload(hass, enable_custom_integrations):
    """Exercise HA's entity registry and actual platform lifecycle, not mocks."""
    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(
        domain="llmvision",
        title="Private account title",
        data={"provider": "OpenAI", "api_key": "PRIVATE-KEY"},
        version=4,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 15
    call_entry = next(
        entity for entity in entities if entity.unique_id.endswith("_usage_calls")
    )
    state = hass.states.get(call_entry.entity_id)
    assert state.state == "unavailable"
    manager = hass.data[USAGE_DATA]
    manager.set_enabled(True)
    args = record_args()
    args["entry_id"] = entry.entry_id
    await manager.async_record(**args)
    await hass.async_block_till_done()
    assert hass.states.get(call_entry.entity_id).state == "1"
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(call_entry.entity_id).state == "1"
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 15
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "stored",
    [
        [],
        "bad",
        {"provider-id": []},
        {"provider-id": {"calls": "5"}},
        {"provider-id": {"calls": True}},
        {"provider-id": {"total_tokens": -1}},
    ],
)
async def test_malformed_existing_storage_is_not_overwritten(enabled_hass, stored):
    manager = UsageManager(enabled_hass)
    with patch.object(manager._store, "async_load", return_value=stored), patch.object(
        manager._store, "async_save", new_callable=AsyncMock
    ) as save:
        await manager.async_load()
        manager.set_enabled(True)
        assert not manager.enabled
        await manager.async_record(**record_args())
        save.assert_not_awaited()
