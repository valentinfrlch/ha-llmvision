import datetime
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.components.calendar.const import CalendarEntityFeature
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .const import SIGNAL_TIMELINE_UPDATED
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
    def icon(self) -> str:  # type: ignore
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

    async def async_added_to_hass(self) -> None:
        """Subscribe to timeline-updated signals so UI state refreshes after writes."""

        @callback
        def _handle_timeline_updated() -> None:
            self.async_schedule_update_ha_state(force_refresh=True)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_TIMELINE_UPDATED, _handle_timeline_updated
            )
        )
    @property
    def extra_state_attributes(self) -> dict:  # type: ignore
        """Return the state attributes"""
        sorted_events = sorted(
            self._events, key=lambda event: event.start, reverse=True
        )
        # Only get most recent event
        event = sorted_events[0] if sorted_events else None
        _LOGGER.debug(f"Most recent event: {event}")

        return {
            "title": event.summary if event else None,
            "description": event.description if event else None,
            "starts": event.start if event else None,
            "ends": event.end if event else None,
            "key_frame": (
                event.location.split(",")[0] if event and event.location else None
            ),
            "camera_name": (
                (
                    event.location.split(",")[1]
                    if len(event.location.split(",")) > 1
                    else ""
                )
                if event and event.location
                else None
            ),
        }

    async def async_update(self) -> None:
        """Loads events from database"""
        await self.timeline.load_events()
        events = await self.timeline.get_all_events()
        calendar_events: list[CalendarEvent] = []
        for event in events:
            if event.start is None or event.end is None:
                continue
            event_start = self._ensure_datetime(event.start)
            event_end = self._ensure_datetime(event.end)
            key_frame = getattr(event, "key_frame", "") or ""
            camera_name = getattr(event, "camera_name", "") or ""
            calendar_events.append(
                CalendarEvent(
                    uid=event.uid,
                    summary=event.title,
                    start=event_start,
                    end=event_end,
                    description=event.description,
                    location=f"{key_frame},{camera_name}",
                )
            )
        calendar_events.sort(
            key=lambda calendar_event: calendar_event.start, reverse=True
        )
        self._events = calendar_events

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Returns calendar events within a datetime range"""
        await self.timeline.load_events()
        timeline_events = await self.timeline.get_all_events()
        calendar_events: list[CalendarEvent] = []

        # Ensure start_date and end_date are datetime.datetime objects and timezone-aware
        start_date = self._ensure_datetime(start_date)
        end_date = self._ensure_datetime(end_date)

        for event in timeline_events:
            if event.start is None or event.end is None:
                continue
            # Ensure event.end and event.start are datetime.datetime objects and timezone-aware
            event_end = self._ensure_datetime(event.end)
            event_start = self._ensure_datetime(event.start)

            if event_end > start_date and event_start < end_date:
                calendar_event = CalendarEvent(
                    uid=event.uid,
                    summary=event.title,
                    start=event_start,
                    end=event_end,
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
        self.async_schedule_update_ha_state(force_refresh=True)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    calendar_entity = Calendar(hass, config_entry)
    async_add_entities([calendar_entity])
