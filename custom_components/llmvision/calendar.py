import aiosqlite
import datetime
import uuid
import os
import json
from .const import DOMAIN, CONF_RETENTION_TIME
from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEvent,
    CalendarEntityFeature,
    EVENT_DESCRIPTION,
    EVENT_END,
    EVENT_LOCATION,
    EVENT_START,
    EVENT_SUMMARY,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
import logging

_LOGGER = logging.getLogger(__name__)


class Timeline(CalendarEntity):
    """Representation of a Calendar."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the calendar"""
        self.hass = hass
        self._attr_name = config_entry.title
        self._attr_unique_id = config_entry.entry_id
        self._events = []
        self._retention_time = self.hass.data.get(DOMAIN).get(
            self._attr_unique_id).get(CONF_RETENTION_TIME)
        self._current_event = None
        self._attr_supported_features = (CalendarEntityFeature.DELETE_EVENT)

        # Path to the JSON file where events are stored
        self._db_path = os.path.join(
            self.hass.config.path("llmvision"), "events.db"
        )
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        
        self.hass.loop.create_task(self.async_update())
        self.hass.async_create_task(self._migrate())  # Run migration if needed

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend"""
        return "mdi:timeline-outline"

    async def _migrate(self):
        # Migrate events from events.json to events.db
        old_db_path = os.path.join(
            self.hass.config.path("llmvision"), "events.json"
        )
        if os.path.exists(old_db_path):
            _LOGGER.info("Migrating events from events.json to events.db")
            with open(old_db_path, "r") as file:
                data = json.load(file)
                event_counter = 0
                for event in data:
                    await self.hass.loop.create_task(self.async_create_event(
                        dtstart=datetime.datetime.fromisoformat(
                            event["start"]),
                        dtend=datetime.datetime.fromisoformat(event["end"]),
                        summary=event["summary"],
                        description=event["description"],
                        key_frame=event["location"].split(",")[0],
                        camera_name=event["location"].split(",")[1] if len(
                            event["location"].split(",")) > 1 else ""
                    ))
                    event_counter += 1
                _LOGGER.info(f"Migrated {event_counter} events")
            _LOGGER.info("Migration complete, deleting events.json")
            os.remove(old_db_path)

    @property
    def extra_state_attributes(self):
        """Return the state attributes"""
        sorted_events = sorted(
            self._events, key=lambda event: event.start, reverse=True)
        # Set limit to 10 newest events to improve performance
        events = sorted_events[:10]
        return {
            "events": [event.summary for event in events],
            "starts": [event.start for event in events],
            "ends": [event.end for event in events],
            "summaries": [event.description for event in events],
            "key_frames": [event.location.split(",")[0] for event in events],
            "camera_names": [event.location.split(",")[1] if len(event.location.split(",")) > 1 else "" for event in events],
        }

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

    async def _delete_image(self, event_id: str):
        """Deletes the image associated with the event"""
        for event in self._events:
            if event.uid == event_id:
                image_path = event.location.split(",")[0]
                _LOGGER.info(f"Image path: {image_path}")
                if os.path.exists(image_path) and "/llmvision/" in image_path:
                    os.remove(image_path)
                    _LOGGER.info(f"Deleted image: {image_path}")
    @property
    async def linked_images(self):
        """Returns the filenames of key_frames associated with events"""
        await self.async_update()
        return [os.path.basename(event.location.split(",")[0]) for event in self._events]
    
    async def _initialize_db(self):
        """Initialize database"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS events (
                        uid TEXT PRIMARY KEY,
                        summary TEXT,
                        start TEXT,
                        end TEXT,
                        description TEXT,
                        key_frame TEXT,
                        camera_name TEXT
                    )
                ''')
                await db.execute('''
                    CREATE INDEX IF NOT EXISTS idx_start ON events (start)
                ''')
                await db.execute('''
                    CREATE INDEX IF NOT EXISTS idx_end ON events (end)
                ''')
                await db.commit()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error initializing database: {e}")

    async def async_update(self) -> None:
        """Loads events from database"""
        await self._initialize_db()
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute('SELECT * FROM events') as cursor:
                rows = await cursor.fetchall()
                self._events = [
                    CalendarEvent(
                        uid=row[0],
                        summary=row[1],
                        start=dt_util.as_local(dt_util.parse_datetime(row[2])),
                        end=dt_util.as_local(dt_util.parse_datetime(row[3])),
                        description=row[4],
                        location=row[5] + "," + row[6] if row[6] else ""
                    )
                    for row in rows
                ]

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Returns calendar events within a datetime range"""
        events = []

        # Ensure start_date and end_date are datetime.datetime objects and timezone-aware
        start_date = self._ensure_datetime(start_date)
        end_date = self._ensure_datetime(end_date)

        for event in self._events:
            # Ensure event.end and event.start are datetime.datetime objects and timezone-aware
            event_end = self._ensure_datetime(event.end)
            event_start = self._ensure_datetime(event.start)

            if event_end > start_date and event_start < end_date:
                events.append(event)
        return events

    async def async_create_event(self, **kwargs: any) -> None:
        """Adds a new event to calendar"""
        await self.async_update()
        dtstart = kwargs[EVENT_START]
        dtend = kwargs[EVENT_END]
        start: datetime.datetime
        end: datetime.datetime
        summary = kwargs[EVENT_SUMMARY]
        description = kwargs.get(EVENT_DESCRIPTION)
        key_frame = kwargs.get("key_frame", "")
        camera_name = kwargs.get("camera_name", "")

        # Ensure dtstart and dtend are datetime objects
        if isinstance(dtstart, str):
            dtstart = datetime.datetime.fromisoformat(dtstart)
        if isinstance(dtend, str):
            dtend = datetime.datetime.fromisoformat(dtend)

        start = dt_util.as_local(dtstart)
        end = dt_util.as_local(dtend)

        event = CalendarEvent(
            uid=str(uuid.uuid4()),
            summary=summary,
            start=start,
            end=end,
            description=description,
            location=f"{key_frame},{camera_name}"
        )

        self._events.append(event)
        await self._save_events()

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Deletes an event on the calendar."""
        _LOGGER.info(f"Deleting event with UID: {uid}")
        await self.async_update()
        await self._delete_image(uid)
        self._events = [event for event in self._events if event.uid != uid]
        await self._save_events()

    async def _save_events(self) -> None:
        """Saves events to database"""
        await self._initialize_db()
        now = datetime.datetime.now()
        cutoff_date = now - datetime.timedelta(days=self._retention_time)
    
        if self._retention_time != 0:
            _LOGGER.info(f"Deleting events before {cutoff_date}")
    
        remaining_events = []
        for event in self._events:
            event_end = dt_util.as_local(self._ensure_datetime(event.end))
            if event_end >= self._ensure_datetime(cutoff_date) or self._retention_time == 0:
                remaining_events.append(event)
            else:
                await self._delete_image(event.uid)
    
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute('DELETE FROM events')
                await db.executemany('''
                    INSERT INTO events (uid, summary, start, end, description, key_frame, camera_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', [
                    (
                        event.uid,
                        event.summary,
                        dt_util.as_local(self._ensure_datetime(
                            event.start)).isoformat(),
                        dt_util.as_local(self._ensure_datetime(
                            event.end)).isoformat(),
                        event.description,
                        event.location.split(",")[0],
                        event.location.split(",")[1] if len(
                            event.location.split(",")) > 1 else ""
                    )
                    for event in remaining_events
                ])
                await db.commit()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error saving events to database: {e}")
    
        # Update calendar entity
        await self.async_update()

    async def remember(self, start, end, label, key_frame, summary, camera_name=""):
        """Remembers the event"""
        await self.async_create_event(
            dtstart=start,
            dtend=end,
            summary=label,
            description=summary,
            key_frame=key_frame,
            camera_name=camera_name
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    calendar_entity = Timeline(hass, config_entry)
    async_add_entities([calendar_entity])
