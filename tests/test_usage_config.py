"""Global usage tracking is opt-in and compatible with existing settings."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from homeassistant import config_entries

from custom_components.llmvision.config_flow import llmvisionConfigFlow
from custom_components.llmvision.const import (
    CONF_MEMORY_PATHS,
    CONF_MEMORY_STRINGS,
    CONF_PROVIDER,
    CONF_REQUEST_TIMEOUT,
    CONF_SYSTEM_PROMPT,
    CONF_TRACK_USAGE,
)


@pytest.fixture
def usage_flow(mock_hass):
    """Build a flow using the real schema and suggested-value helpers."""
    flow = llmvisionConfigFlow()
    flow.hass = mock_hass
    flow.context = {"source": config_entries.SOURCE_USER}
    flow.async_show_form = Mock(side_effect=lambda **kwargs: kwargs)
    flow.async_create_entry = Mock(side_effect=lambda **kwargs: kwargs)
    return flow


async def test_initial_setup_tracking_defaults_off(usage_flow):
    """The first setup form and stored entry both default to disabled."""
    form = await usage_flow.async_step_user()
    assert form["step_id"] == "settings"
    data = form["data_schema"]({"general_section": {}})
    assert data["general_section"][CONF_TRACK_USAGE] is False
    entry = await usage_flow.async_step_settings(data)
    assert entry["data"][CONF_TRACK_USAGE] is False
    assert entry["data"][CONF_PROVIDER] == "Settings"


@pytest.mark.parametrize("enabled", [False, True])
async def test_setup_saves_explicit_tracking_choice(usage_flow, enabled):
    await usage_flow.async_step_user()
    result = await usage_flow.async_step_settings(
        {"general_section": {CONF_TRACK_USAGE: enabled}}
    )
    assert result["data"][CONF_TRACK_USAGE] is enabled


async def test_legacy_setup_without_tracking_stays_disabled(usage_flow):
    await usage_flow.async_step_user()
    result = await usage_flow.async_step_settings(
        {"general_section": {CONF_REQUEST_TIMEOUT: 120}}
    )
    assert result["data"][CONF_TRACK_USAGE] is False
    assert result["data"][CONF_REQUEST_TIMEOUT] == 120


@pytest.mark.parametrize("saved", [None, False, True])
async def test_reconfigure_suggests_saved_tracking_or_false(usage_flow, saved):
    usage_flow.context = {"source": config_entries.SOURCE_RECONFIGURE}
    data = {CONF_PROVIDER: "Settings"}
    if saved is not None:
        data[CONF_TRACK_USAGE] = saved
    usage_flow._get_reconfigure_entry = Mock(return_value=Mock(data=data))
    form = await usage_flow.async_step_reconfigure({})
    general_schema = form["data_schema"].schema["general_section"].schema
    key = next(key for key in general_schema.schema if key == CONF_TRACK_USAGE)
    assert key.description["suggested_value"] is (saved or False)


@pytest.mark.parametrize(
    "saved, submitted, expected",
    [
        (None, None, False),
        (True, None, True),
        (False, True, True),
        (True, False, False),
    ],
)
async def test_reconfigure_preserves_unrelated_settings(
    usage_flow, saved, submitted, expected
):
    """Only submitted fields and the defaulted opt-in should change."""
    existing = {
        CONF_PROVIDER: "Settings",
        CONF_SYSTEM_PROMPT: "Keep my system prompt",
        CONF_REQUEST_TIMEOUT: 120,
        CONF_MEMORY_PATHS: ["/mock/reference.jpg"],
        CONF_MEMORY_STRINGS: ["My front door"],
        "memory_images_encoded": ["previously encoded image"],
    }
    if saved is not None:
        existing[CONF_TRACK_USAGE] = saved
    original = dict(existing)
    entry = Mock(data=existing)
    usage_flow.context = {"source": config_entries.SOURCE_RECONFIGURE}
    usage_flow._get_reconfigure_entry = Mock(return_value=entry)
    # Model Home Assistant's data_updates merge without reloading any providers.
    usage_flow.async_update_reload_and_abort = Mock(
        side_effect=lambda entry, data_updates: {**entry.data, **data_updates}
    )
    submitted_data = {} if submitted is None else {CONF_TRACK_USAGE: submitted}
    with patch(
        "custom_components.llmvision.config_flow.os.path.exists", return_value=True
    ):
        result = await usage_flow.async_step_settings(
            {"general_section": submitted_data}
        )
    assert result == {**original, CONF_TRACK_USAGE: expected}
    assert existing == original


async def test_reconfigure_can_still_clear_memory(usage_flow):
    usage_flow.context = {"source": config_entries.SOURCE_RECONFIGURE}
    entry = Mock(
        data={
            CONF_PROVIDER: "Settings",
            CONF_MEMORY_PATHS: ["old.jpg"],
            CONF_MEMORY_STRINGS: ["Old image"],
            CONF_TRACK_USAGE: True,
        }
    )
    usage_flow._get_reconfigure_entry = Mock(return_value=entry)
    usage_flow.async_update_reload_and_abort = Mock(
        side_effect=lambda entry, data_updates: data_updates
    )
    result = await usage_flow.async_step_settings(
        {"memory_section": {CONF_MEMORY_PATHS: [], CONF_MEMORY_STRINGS: []}}
    )
    assert result[CONF_MEMORY_PATHS] == []
    assert result[CONF_MEMORY_STRINGS] == []
    assert result[CONF_TRACK_USAGE] is True


@pytest.mark.parametrize("filename", ["strings.json", "translations/en.json"])
def test_tracking_copy_explains_privacy(filename):
    root = Path(__file__).parents[1] / "custom_components/llmvision"
    strings = json.loads((root / filename).read_text())
    general = strings["config"]["step"]["settings"]["sections"]["general_section"]
    assert general["data"][CONF_TRACK_USAGE] == "Track token usage"
    description = general["data_description"][CONF_TRACK_USAGE]
    assert "provider-reported" in description
    assert "locally" in description
    assert "no additional model calls" in description
    assert "no prompts or images" in description
