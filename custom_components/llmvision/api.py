import json
import logging
from datetime import datetime, timedelta
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.json import json_dumps
from homeassistant.util import dt as dt_util
from .calendar import Timeline
from .const import DOMAIN, CONF_PROVIDER, CONF_RETENTION_TIME

_LOGGER = logging.getLogger(__name__)


async def async_get_settings_entry(hass):
    """Return the Settings config entry, or None if not found"""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_PROVIDER) == "Settings":
            return entry
    return None


class TimelineEventsView(HomeAssistantView):
    """View to handle timeline events.
    Returns:
        - 200: List of events
    """

    url = "/api/llmvision/timeline/events"
    name = "api:llmvision:timeline:events"
    requires_auth = True

    async def get(self, request):
        hass = request.app["hass"]

        settings_entry = await async_get_settings_entry(hass)
        # Parse request params
        try:
            # Limit: minimum 1, maximum 100
            limit = max(1, min(int(request.query.get("limit", 10)), 100))
        except ValueError:
            limit = 10

        cameras = request.query.get("cameras", None)
        categories = request.query.get("categories", None)
        days = request.query.get("days", None)

        def _parse_list_param(val):
            if val is None:
                return None
            if isinstance(val, str):
                parts = [p.strip() for p in val.split(",") if p.strip()]
                return parts if parts else None
            # if already a list-like, normalize items to str
            try:
                return [str(p).strip() for p in val if str(p).strip()]
            except Exception:
                return None

        cameras = _parse_list_param(cameras)
        categories = _parse_list_param(categories)
        start = None
        end = None

        # If days is provided, calculate start and end dates
        if days is not None:
            try:
                days = int(days)
                end_date = dt_util.now()
                start_date = end_date - timedelta(days=days)
                start = start_date.isoformat()
                end = end_date.isoformat()
            except ValueError:
                start = None
                end = None

        timeline = Timeline(hass, settings_entry)
        events = await timeline.get_events_json(
            limit=limit,
            cameras=cameras,
            categories=categories,
            start=start,
            end=end,
        )
        return self.json({"events": json.loads(json_dumps(events))})


class TimelineEventCreateView(HomeAssistantView):
    """View to create a new timeline event via POST."""

    url = "/api/llmvision/timeline/events/new"
    name = "api:llmvision:timeline:events:new"
    requires_auth = True

    async def post(self, request):
        hass = request.app["hass"]
        settings_entry = await async_get_settings_entry(hass)
        if settings_entry is None:
            return self.json_message("Settings config entry not found", status_code=404)

        try:
            data = await request.json()
        except Exception:
            return self.json_message("Invalid JSON body", status_code=400)

        # Parse and validate inputs
        label = data.get("label") or "Untitled event"
        summary = data.get("summary") or ""
        category = data.get("category") or ""
        key_frame = data.get("key_frame") or ""
        camera_name = data.get("camera_name") or data.get("camera_entity") or ""
        today_summary = data.get("today_summary") or ""

        # Times: accept ISO strings or timestamps; default to now..now+1min
        def _parse_time(val):
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val)
            if isinstance(val, str):
                dt = dt_util.parse_datetime(val)
                if dt is None:
                    # Try fromisoformat fallback (naive)
                    try:
                        return datetime.fromisoformat(val)
                    except Exception:
                        return None
                return dt
            if isinstance(val, datetime):
                return val
            return None

        start = _parse_time(data.get("start")) or dt_util.now()
        end = _parse_time(data.get("end")) or (start + timedelta(minutes=1))

        timeline = Timeline(hass, settings_entry)
        try:
            await timeline.create_event(
                start=start,
                end=end,
                label=label,
                summary=summary,
                category=category,
                key_frame=key_frame,
                camera_name=camera_name,
                today_summary=today_summary,
            )
        except Exception as e:
            _LOGGER.error(f"Error creating timeline event: {e}")
            return self.json_message("Error creating event", status_code=500)

        # Optionally return the most recent event
        try:
            recent = await timeline.get_events_json(limit=1)
            payload = {
                "status": "created",
                "event": json.loads(json_dumps(recent[0])) if recent else None,
            }
        except Exception:
            payload = {"status": "created"}

        return self.json(payload)


class TimelineEventView(HomeAssistantView):
    """View to handle individual timeline events.
    Parameters:
        - event_id: ID of the event to delete (uid)
    Returns:
        - 200: Event deleted successfully
        - 404: Event not found
        - 500: Error deleting event
    """

    url = "/api/llmvision/timeline/event/{event_id}"
    name = "api:llmvision:timeline:event"
    requires_auth = True

    async def get(self, request, event_id):
        hass = request.app["hass"]
        settings_entry = await async_get_settings_entry(hass)
        if settings_entry is None:
            return self.json_message("Settings config entry not found", status_code=404)
        timeline = Timeline(hass, settings_entry)
        event = await timeline.get_event(event_id)
        if event is None:
            return self.json_message("Event not found", status_code=404)
        return self.json({"event": json.loads(json_dumps(event))})

    async def delete(self, request, event_id):
        hass = request.app["hass"]
        settings_entry = await async_get_settings_entry(hass)
        if settings_entry is None:
            return self.json_message("Settings config entry not found", status_code=404)
        timeline = Timeline(hass, settings_entry)
        try:
            await timeline.delete_event(event_id)
        except Exception as e:
            _LOGGER.error(f"Error deleting event {event_id}: {e}")
            return self.json_message("Error deleting event", status_code=500)
        return self.json({"event_id": event_id, "status": "deleted"})