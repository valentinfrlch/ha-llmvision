import datetime
from homeassistant.core import HomeAssistant
from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEvent,
    CalendarEntityFeature,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .timeline import Timeline
import logging

_LOGGER = logging.getLogger(__name__)


class Calendar(CalendarEntity):
    """Representation of a Calendar."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the calendar"""
        self.hass = hass
        self._attr_name = "LLM Vision Timeline"
        self._attr_unique_id = "llm_vision_timeline"
        self.timeline = Timeline(hass, config_entry=config_entry)
        self._events = []
        self._current_event = None
        self._attr_supported_features = CalendarEntityFeature.DELETE_EVENT

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend"""
        return "mdi:timeline-outline"

    @property
    def event(self):
        """Return the current event"""
        return self._current_event

    def _ensure_datetime(self, dt):
        """Ensures the input is a datetime.datetime object"""
        if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
            dt = datetime.datetime.combine(dt, datetime.datetime.min.time())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt

    async def async_update(self) -> None:
        """Loads events from database"""
        events = await self.timeline.get_all_events()
        self._events = [
            CalendarEvent(
                uid=event.uid,
                summary=event.title,
                start=event.start,
                end=event.end,
                description=event.description,
            )
            for event in events
        ]
        self._events.sort(key=lambda event: event.start, reverse=True)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Returns calendar events within a datetime range"""
        timeline_events = await self.timeline.get_all_events()
        calendar_events: list[CalendarEvent] = []

        # Ensure start_date and end_date are datetime.datetime objects and timezone-aware
        start_date = self._ensure_datetime(start_date)
        end_date = self._ensure_datetime(end_date)

        for event in timeline_events:
            # Ensure event.end and event.start are datetime.datetime objects and timezone-aware
            event_end = self._ensure_datetime(event.end)
            event_start = self._ensure_datetime(event.start)

            if event_end > start_date and event_start < end_date:
                calendar_event = CalendarEvent(
                    uid=event.uid,
                    summary=event.title,
                    start=event.start,
                    end=event.end,
                    description=event.description,
                )
                calendar_events.append(calendar_event)
        return calendar_events

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Deletes an event from the calendar."""
        _LOGGER.info(f"Deleting event with UID: {uid}")
        await self.timeline.delete_event(uid)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    calendar_entity = Calendar(hass, config_entry)
    async_add_entities([calendar_entity])
