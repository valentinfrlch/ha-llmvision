"""Exercise accounting at real orchestration and transport boundaries.

Only payload construction and network/SDK transports are mocked. Keeping
Request.call, provider parsing and the accounting wrapper real catches double
counting that isolated normalizer tests cannot detect.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.llmvision.providers import AWSBedrock, OpenAI, Request
from custom_components.llmvision.usage import (
    EVENT_CALL_FINISHED,
    EVENT_TOKEN_USAGE,
    async_get_manager,
)

PROVIDERS_MODULE = "custom_components.llmvision.providers"


def collect_events(hass: HomeAssistant, event_type: str) -> list[Event]:
    """Collect on the event loop, preserving publication order deterministically."""
    events: list[Event] = []

    # Plain list.append is an unmarked synchronous listener: Home Assistant runs
    # it in executor threads, whose completion order is not event publication
    # order. This callback does no blocking work and belongs on the event loop.
    @callback
    def append_event(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen(event_type, append_event)
    return events


@pytest.fixture
def tracking_hass(hass):
    """Configure two distinct accounts so fallback attribution cannot collapse."""
    MockConfigEntry(
        domain="llmvision",
        data={
            "provider": "Settings",
            "track_usage": True,
            "fallback_provider": "backup",
        },
    ).add_to_hass(hass)
    hass.data["llmvision"] = {
        "primary": {"provider": "OpenAI", "default_model": "primary-model"},
        "backup": {"provider": "OpenAI", "default_model": "backup-model"},
    }
    return hass


def make_call(**overrides):
    """Supply only the service fields needed by Request.call and its observer."""
    fields = dict(
        provider="primary",
        model=None,
        message="PRIVATE PROMPT",
        max_tokens=64,
        service="image_analyzer",
        context=Context(),
        generate_title=False,
        response_format="text",
        title_field=None,
        memory=SimpleNamespace(title_prompt="PRIVATE TITLE INSTRUCTION"),
        model_is_glimpse=lambda: False,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def completion(content="Analysis", *, tokens=10, status=200):
    return Mock(
        status=status,
        json=AsyncMock(
            return_value={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": tokens,
                    "completion_tokens": 2,
                    "total_tokens": tokens + 2,
                },
            }
        ),
    )


async def run_request(hass, call, responses):
    """Use the actual provider factory, preventing a mock from hiding attribution."""
    session = SimpleNamespace(post=AsyncMock(side_effect=responses))
    with (
        patch(f"{PROVIDERS_MODULE}.async_get_clientsession", return_value=session),
        patch.object(OpenAI, "_prepare_vision_data", return_value={}),
        patch.object(OpenAI, "_prepare_text_data", return_value={}),
    ):
        request = Request(hass, "PRIVATE PROMPT", 64, 0.5)
        request.add_frame("PRIVATE IMAGE", "PRIVATE CAMERA")
        result = await request.call(call)
    return result, session


async def test_fallback_counts_each_attempt_on_its_own_provider(tracking_hass):
    manager = await async_get_manager(tracking_hass)
    finished = collect_events(tracking_hass, EVENT_CALL_FINISHED)
    call = make_call()
    result, session = await run_request(
        tracking_hass,
        call,
        [completion(status=429), completion("Fallback answer", tokens=20)],
    )
    await tracking_hass.async_block_till_done()
    assert result == {"response_text": "Fallback answer"}
    assert session.post.await_count == 2
    primary, backup = (manager.get_totals(key) for key in ("primary", "backup"))
    assert (
        primary["calls"],
        primary["errors"],
        primary["missing_usage"],
        primary["total_tokens"],
    ) == (1, 1, 1, 0)
    assert (backup["calls"], backup["errors"], backup["total_tokens"]) == (1, 0, 22)
    assert [event.data["config_entry_id"] for event in finished] == [
        "primary",
        "backup",
    ]
    assert [event.data["model"] for event in finished] == [
        "primary-model",
        "backup-model",
    ]
    assert all(event.context is call.context for event in finished)


async def test_title_failure_fallback_accounts_for_repeated_analysis(tracking_hass):
    """Existing fallback reruns analysis; account for all four actual requests."""
    manager = await async_get_manager(tracking_hass)
    finished = collect_events(tracking_hass, EVENT_CALL_FINISHED)
    result, session = await run_request(
        tracking_hass,
        make_call(generate_title=True),
        [
            completion(tokens=10),
            completion(status=503),
            completion(tokens=20),
            completion("Fallback title", tokens=30),
        ],
    )
    await tracking_hass.async_block_till_done()
    assert result == {"response_text": "Analysis", "title": "Fallback title"}
    assert session.post.await_count == 4
    primary, backup = (manager.get_totals(key) for key in ("primary", "backup"))
    assert (
        primary["calls"],
        primary["errors"],
        primary["analysis_total_tokens"],
        primary["title_total_tokens"],
    ) == (2, 1, 12, 0)
    assert (
        backup["calls"],
        backup["errors"],
        backup["analysis_total_tokens"],
        backup["title_total_tokens"],
    ) == (2, 0, 22, 32)
    assert [event.data["request_type"] for event in finished] == [
        "analysis",
        "title",
        "analysis",
        "title",
    ]
    assert primary["total_tokens"] + backup["total_tokens"] == 66


@pytest.mark.parametrize("glimpse", [False, True], ids=["structured", "glimpse"])
async def test_embedded_title_never_adds_a_title_call(tracking_hass, glimpse):
    manager = await async_get_manager(tracking_hass)
    call = make_call(
        generate_title=True,
        response_format="text" if glimpse else "json",
        title_field="title",
        model_is_glimpse=lambda: glimpse,
    )
    content = '{"title": "A visitor", "description": "Someone arrived"}'
    result, session = await run_request(tracking_hass, call, [completion(content)])
    assert result["title"] == "A visitor"
    if glimpse:
        assert result["response_text"] == "Someone arrived"
    else:
        assert result["structured_response"]["description"] == "Someone arrived"
    totals = manager.get_totals("primary")
    assert session.post.await_count == 1
    assert (
        totals["calls"],
        totals["analysis_total_tokens"],
        totals["title_total_tokens"],
    ) == (1, 12, 0)
    assert manager.get_totals("backup")["calls"] == 0


@pytest.mark.parametrize("bearer", [False, True], ids=["iam", "bearer"])
@pytest.mark.parametrize("metrics", ["core", "cache", "missing"])
async def test_bedrock_transports_capture_usage_before_output_extraction(
    tracking_hass, bearer, metrics
):
    """IAM returns output-only to parsing, so observe its original SDK response.

    Cache and reasoning fields are optional. Their absence must not discard valid
    core metrics, and an absent usage block must never fabricate token usage.
    """
    tracking_hass.data["llmvision"]["primary"] = {"provider": "AWS Bedrock"}
    manager = await async_get_manager(tracking_hass)
    events = collect_events(tracking_hass, EVENT_TOKEN_USAGE)
    body = {
        "output": {"message": {"content": [{"text": "Bedrock answer"}]}},
        "ResponseMetadata": {"HTTPStatusCode": 200},
    }
    if metrics != "missing":
        body["usage"] = {"inputTokens": 10, "outputTokens": 2, "totalTokens": 12}
        if metrics == "cache":
            body["usage"].update(cacheReadInputTokens=3, cacheWriteInputTokens=4)
    client = Mock(converse=Mock(return_value=body))
    session = SimpleNamespace(
        post=AsyncMock(return_value=Mock(status=200, json=AsyncMock(return_value=body)))
    )
    with (
        patch(f"{PROVIDERS_MODULE}.async_get_clientsession", return_value=session),
        patch(f"{PROVIDERS_MODULE}.boto3.client", return_value=client) as create_client,
    ):
        provider = AWSBedrock(
            tracking_hass,
            "test-access",
            "test-secret",
            "us-east-1",
            "test-model",
            api_key="test-bearer" if bearer else None,
        )
        provider._prepare_vision_data = Mock(
            return_value={"messages": [], "inferenceConfig": {}}
        )
        assert (
            await provider.vision_request(make_call(model="test-model"))
            == "Bedrock answer"
        )
    await tracking_hass.async_block_till_done()
    assert session.post.await_count == int(bearer)
    assert client.converse.call_count == int(not bearer)
    assert create_client.call_count == int(not bearer)
    totals = manager.get_totals("primary")
    assert (totals["calls"], totals["errors"], totals["missing_usage"]) == (
        1,
        0,
        int(metrics == "missing"),
    )
    assert totals["total_tokens"] == {"core": 12, "cache": 19, "missing": 0}[metrics]
    assert totals["cache_read_tokens"] == (3 if metrics == "cache" else 0)
    assert totals["cache_write_tokens"] == (4 if metrics == "cache" else 0)
    assert totals["reasoning_tokens"] == 0
    assert len(events) == int(metrics != "missing")
    if events:
        assert "reasoning_tokens" not in events[0].data
        if metrics == "core":
            assert "cache_read_tokens" not in events[0].data
            assert "cache_write_tokens" not in events[0].data


@pytest.mark.parametrize("bearer", [False, True], ids=["iam", "bearer"])
async def test_bedrock_transport_failure_counts_attempt_not_tokens(
    tracking_hass, bearer
):
    tracking_hass.data["llmvision"]["primary"] = {"provider": "AWS Bedrock"}
    manager = await async_get_manager(tracking_hass)
    session = SimpleNamespace(post=AsyncMock(side_effect=TimeoutError("PRIVATE")))
    client = Mock(converse=Mock(side_effect=TimeoutError("PRIVATE")))
    with (
        patch(f"{PROVIDERS_MODULE}.async_get_clientsession", return_value=session),
        patch(f"{PROVIDERS_MODULE}.boto3.client", return_value=client),
    ):
        provider = AWSBedrock(
            tracking_hass,
            "test-access",
            "test-secret",
            "us-east-1",
            "test-model",
            api_key="test-bearer" if bearer else None,
        )
        provider._prepare_vision_data = Mock(return_value={})
        with pytest.raises(ServiceValidationError):
            await provider.vision_request(make_call(model="test-model"))
    totals = manager.get_totals("primary")
    assert (
        totals["calls"],
        totals["errors"],
        totals["missing_usage"],
        totals["total_tokens"],
    ) == (1, 1, 1, 0)
