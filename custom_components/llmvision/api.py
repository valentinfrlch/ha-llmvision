import json
import logging
from datetime import datetime, timedelta
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.json import json_dumps
from homeassistant.util import dt as dt_util
from .calendar import Timeline
from .const import DOMAIN, CONF_PROVIDER

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
        title = data.get("title") or ""
        description = data.get("description") or ""
        key_frame = data.get("key_frame") or ""
        camera_name = data.get("camera_name") or data.get("camera_entity") or ""
        label = data.get("label") or ""

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
                title=title,
                description=description,
                key_frame=key_frame,
                camera_name=camera_name,
                label=label.lower(),
            )
        except Exception as e:
            _LOGGER.error(f"Error creating timeline event: {e}")
            return self.json_message("Error creating event", status_code=500)

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
        event: dict = await timeline.get_event(event_id)
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

    async def post(self, request, event_id):
        """Update an existing timeline event."""
        hass = request.app["hass"]
        settings_entry = await async_get_settings_entry(hass)
        if settings_entry is None:
            return self.json_message("Settings config entry not found", status_code=404)

        try:
            data = await request.json()
        except Exception:
            return self.json_message("Invalid JSON body", status_code=400)

        timeline = Timeline(hass, settings_entry)

        # Ensure the event exists
        try:
            existing = await timeline.get_event(event_id)
        except Exception as e:
            _LOGGER.error(f"Error retrieving event {event_id}: {e}")
            return self.json_message("Error retrieving event", status_code=500)

        if existing is None:
            return self.json_message("Event not found", status_code=404)

        # Local time parser
        def _parse_time(val):
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val)
            if isinstance(val, str):
                dt = dt_util.parse_datetime(val)
                if dt is None:
                    try:
                        return datetime.fromisoformat(val)
                    except Exception:
                        return None
                return dt
            if isinstance(val, datetime):
                return val
            return None

        fields = {
            "title": data.get("title", existing.get("title", "")),
            "description": data.get("description", existing.get("description", "")),
            "key_frame": data.get("key_frame", existing.get("key_frame", "")),
            "camera_name": data.get(
                "camera_name",
                data.get("camera_entity", existing.get("camera_name", "")),
            ),
            "label": data.get("label", existing.get("label", "")),
        }

        start_in = data.get("start", existing.get("start"))
        end_in = data.get("end", existing.get("end"))
        start_dt = _parse_time(start_in)
        end_dt = _parse_time(end_in)

        if start_dt is None or end_dt is None:
            return self.json_message("Invalid start/end time", status_code=400)

        try:
            await timeline.update_event(
                uid=event_id,
                start=start_dt,
                end=end_dt,
                title=fields["title"],
                description=fields["description"],
                key_frame=fields["key_frame"],
                camera_name=fields["camera_name"],
                label=fields["label"].lower(),
            )
        except Exception as e:
            _LOGGER.error(f"Error updating event {event_id}: {e}")
            return self.json_message("Error updating event", status_code=500)

        try:
            updated = await timeline.get_event_json(event_id)
            return self.json({"event": json.loads(json_dumps(updated))})
        except Exception:
            return self.json({"event_id": event_id, "status": "updated"})
