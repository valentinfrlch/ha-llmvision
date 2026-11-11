"""Tests for privacy-preserving provider usage entities."""

from unittest.mock import Mock, patch

import pytest
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.llmvision.const import DOMAIN
from custom_components.llmvision.sensor import (
    SENSOR_DESCRIPTIONS,
    UsageSensor,
    async_setup_entry,
)
from custom_components.llmvision.usage import SIGNAL_USAGE_UPDATED, USAGE_DATA


@pytest.fixture
def provider_entry():
    """A provider entry deliberately containing values that must stay private."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="provider-one",
        title="Secret endpoint label",
        data={"provider": "OpenAI", "api_key": "private-api-key"},
    )


@pytest.fixture
def manager():
    manager = Mock()
    manager.enabled = True
    manager.get_totals.return_value = {
        description.key: index + 1
        for index, description in enumerate(SENSOR_DESCRIPTIONS)
    }
    return manager


async def test_setup_provider_sensors(hass, provider_entry, manager):
    """Provider entities have stable IDs, diagnostic metadata and safe attributes."""
    hass.data[USAGE_DATA] = manager
    entities = []
    await async_setup_entry(hass, provider_entry, entities.extend)
    assert len(entities) == 15
    assert len({entity.unique_id for entity in entities}) == 15
    for entity in entities:
        key = entity.entity_description.key
        assert entity.unique_id == f"provider-one_usage_{key}"
        assert entity.state_class == SensorStateClass.TOTAL_INCREASING
        assert entity.entity_category == EntityCategory.DIAGNOSTIC
        assert entity.device_class is None
        assert entity.should_poll is False
        assert entity.has_entity_name is True
        assert entity.native_unit_of_measurement == (
            "tokens" if "tokens" in key else "calls"
        )
        assert entity.native_value == manager.get_totals.return_value[key]
        assert entity.extra_state_attributes is None
        assert entity.device_info == {
            "identifiers": {(DOMAIN, "provider-one")},
            "name": "LLM Vision OpenAI",
            "manufacturer": "LLM Vision",
        }

    # The display title, API key and user configuration cannot alter registry IDs.
    renamed = MockConfigEntry(
        domain=DOMAIN,
        entry_id=provider_entry.entry_id,
        title="A different title",
        data={"provider": "OpenAI", "api_key": "replacement-key"},
    )
    recreated = []
    await async_setup_entry(hass, renamed, recreated.extend)
    assert [e.unique_id for e in recreated] == [e.unique_id for e in entities]


@pytest.mark.parametrize(
    "provider", ["Settings", "Memory", "Timeline", None, "Unknown"]
)
async def test_non_provider_entries_have_no_sensors(hass, provider):
    """Non-provider entries do not even access the usage manager."""
    entry = MockConfigEntry(domain=DOMAIN, data={"provider": provider})
    add_entities = Mock()
    await async_setup_entry(hass, entry, add_entities)
    add_entities.assert_not_called()


async def test_updates_and_tracking_toggle(hass, provider_entry, manager):
    """Dispatch only relevant updates and retain totals while tracking is off."""
    entity = UsageSensor(manager, provider_entry, SENSOR_DESCRIPTIONS[0])
    entity.hass = hass
    entity.entity_id = "sensor.provider_calls"
    await entity.async_added_to_hass()
    with patch.object(entity, "async_write_ha_state") as write_state:
        async_dispatcher_send(hass, SIGNAL_USAGE_UPDATED, "other-provider")
        await hass.async_block_till_done()
        write_state.assert_not_called()

        manager.get_totals.return_value["calls"] = 42
        async_dispatcher_send(hass, SIGNAL_USAGE_UPDATED, provider_entry.entry_id)
        await hass.async_block_till_done()
        write_state.assert_called_once()
        assert entity.native_value == 42
        assert entity.available

        manager.enabled = False
        async_dispatcher_send(hass, SIGNAL_USAGE_UPDATED, None)
        await hass.async_block_till_done()
        assert write_state.call_count == 2
        assert not entity.available
        assert entity.native_value == 42

        manager.enabled = True
        async_dispatcher_send(hass, SIGNAL_USAGE_UPDATED, None)
        await hass.async_block_till_done()
        assert write_state.call_count == 3
        assert entity.available

        # Entity removal must disconnect its dispatcher subscription.
        await entity.async_remove(force_remove=True)
        async_dispatcher_send(hass, SIGNAL_USAGE_UPDATED, provider_entry.entry_id)
        await hass.async_block_till_done()
        assert write_state.call_count == 3


def test_unseen_provider_starts_at_zero(provider_entry, manager):
    manager.get_totals.return_value = {}
    entity = UsageSensor(manager, provider_entry, SENSOR_DESCRIPTIONS[0])
    assert entity.native_value == 0


@pytest.mark.parametrize("disabled_by", [None, ConfigEntryDisabler.USER])
async def test_provider_startup_respects_disabled_settings(
    hass, enable_custom_integrations, disabled_by
):
    """Restoring a saved opt-in must not reactivate a disabled Settings entry."""
    settings = MockConfigEntry(
        domain=DOMAIN,
        data={"provider": "Settings", "track_usage": True},
        disabled_by=disabled_by,
        version=4,
    )
    settings.add_to_hass(hass)
    provider = MockConfigEntry(
        domain=DOMAIN,
        data={"provider": "OpenAI", "api_key": "test-key"},
        version=4,
    )
    provider.add_to_hass(hass)

    # A fresh manager is created by provider startup, as after an HA restart.
    assert USAGE_DATA not in hass.data
    assert await hass.config_entries.async_setup(provider.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[USAGE_DATA]
    enabled = disabled_by is None
    assert manager.enabled is enabled
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, provider.entry_id)
    assert len(entities) == 15
    calls = next(
        entity for entity in entities if entity.unique_id.endswith("_usage_calls")
    )
    assert hass.states.get(calls.entity_id).state == ("0" if enabled else "unavailable")

    await manager.async_record(
        entry_id=provider.entry_id,
        provider="OpenAI",
        model="test-model",
        service="image_analyzer",
        phase="analysis",
        usage={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
        failed=False,
        duration_ms=1,
    )
    await hass.async_block_till_done()
    assert manager.get_totals(provider.entry_id)["calls"] == int(enabled)
    assert hass.states.get(calls.entity_id).state == ("1" if enabled else "unavailable")
    assert await hass.config_entries.async_unload(provider.entry_id)
