"""Diagnostic usage counters for configured LLM providers."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PROVIDER, DOMAIN
from .usage import (
    SIGNAL_USAGE_UPDATED,
    USAGE_DATA,
    UsageManager,
    is_provider_entry,
)

SENSOR_DESCRIPTIONS = tuple(
    SensorEntityDescription(
        key=key,
        name=name,
        native_unit_of_measurement=unit,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:counter",
    )
    for key, name, unit in (
        ("calls", "API calls", "calls"),
        ("errors", "API errors", "calls"),
        ("missing_usage", "Calls without usage", "calls"),
        ("input_tokens", "Input tokens", "tokens"),
        ("output_tokens", "Output tokens", "tokens"),
        ("total_tokens", "Total tokens", "tokens"),
        ("cache_read_tokens", "Cache read tokens", "tokens"),
        ("cache_write_tokens", "Cache write tokens", "tokens"),
        ("reasoning_tokens", "Reasoning tokens", "tokens"),
        ("analysis_input_tokens", "Analysis input tokens", "tokens"),
        ("analysis_output_tokens", "Analysis output tokens", "tokens"),
        ("analysis_total_tokens", "Analysis total tokens", "tokens"),
        ("title_input_tokens", "Title input tokens", "tokens"),
        ("title_output_tokens", "Title output tokens", "tokens"),
        ("title_total_tokens", "Title total tokens", "tokens"),
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose provider totals already loaded by the integration's usage manager."""
    if not is_provider_entry(entry):
        return
    manager: UsageManager = hass.data[USAGE_DATA]
    async_add_entities(
        UsageSensor(manager, entry, description) for description in SENSOR_DESCRIPTIONS
    )


class UsageSensor(SensorEntity):
    """A persisted counter with no request content or credentials in its state."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        manager: UsageManager,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        self.entity_description = description
        self._manager = manager
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_usage_{description.key}"
        # Use only the provider's label, never the user-editable title or endpoint.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"LLM Vision {entry.data[CONF_PROVIDER]}",
            manufacturer="LLM Vision",
        )

    @property
    def available(self) -> bool:
        """Disabled tracking retains totals without implying fresh measurements."""
        return self._manager.enabled

    @property
    def native_value(self) -> int:
        """Return the durable counter; sensors do not maintain a second copy."""
        return self._manager.get_totals(self._entry_id).get(
            self.entity_description.key, 0
        )

    async def async_added_to_hass(self) -> None:
        """Listen for this provider's changes and global tracking toggles."""
        await super().async_added_to_hass()

        @callback
        def _async_usage_updated(entry_id: str | None) -> None:
            if entry_id is None or entry_id == self._entry_id:
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_USAGE_UPDATED, _async_usage_updated
            )
        )
