import aiosqlite
import shutil
import datetime
import uuid
import os
import json
import asyncio
from .const import DOMAIN, CONF_RETENTION_TIME
from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEvent,
    CalendarEntityFeature,
    EVENT_DESCRIPTION,
    EVENT_END,
    EVENT_START,
    EVENT_SUMMARY,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from functools import partial
import logging

_LOGGER = logging.getLogger(__name__)


class Timeline(CalendarEntity):
    """Representation of a Calendar."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the calendar"""
        self.hass = hass
        self._attr_name = "LLM Vision Timeline"
        self._attr_unique_id = "llm_vision_timeline"
        self._events = []
        self._today_summary = ""
        self._retention_time = config_entry.data.get(CONF_RETENTION_TIME)
        _LOGGER.debug(f"Retention time set to: {self._retention_time} days")
        self._current_event = None
        self._attr_supported_features = CalendarEntityFeature.DELETE_EVENT

        # Track key_frame paths whose DB rows are not yet committed
        self._pending_key_frames: set[str] = set()
        self._cleanup_lock = asyncio.Lock()

        # Path to the JSON file where events are stored
        self._db_path = os.path.join(self.hass.config.path(DOMAIN), "events.db")
        self._file_path = f"/media/{DOMAIN}/snapshots"
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        os.makedirs(self._file_path, exist_ok=True)

        self.hass.loop.create_task(self.async_update()) # Init db, load events and check events for retention
        self.hass.loop.create_task(self._cleanup()) # Cleanup unlinked images
        self.hass.async_create_task(self._migrate())  # Run migration if needed

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend"""
        return "mdi:timeline-outline"

    async def _migrate(self):
        """Handles migration for events.db (current v3)"""
        # v1 -> v2: Migrate events from events.json to events.db
        old_db_path = os.path.join(self.hass.config.path(DOMAIN), "events.json")
        if os.path.exists(old_db_path):
            _LOGGER.info("Migrating events from events.json to events.db")
            with open(old_db_path, "r") as file:
                data = json.load(file)
                event_counter = 0
                for event in data:
                    await self.hass.loop.create_task(
                        self.async_create_event(
                            dtstart=datetime.datetime.fromisoformat(event["start"]),
                            dtend=datetime.datetime.fromisoformat(event["end"]),
                            summary=event["summary"],
                            description=event["description"],
                            key_frame=event["location"].split(",")[0],
                            camera_name=(
                                event["location"].split(",")[1]
                                if len(event["location"].split(",")) > 1
                                else ""
                            ),
                            today_summary="",
                        )
                    )
                    event_counter += 1
                _LOGGER.info(f"Migrated {event_counter} events")
            _LOGGER.info("Migration complete, deleting events.json")
            os.remove(old_db_path)
        # v2 -> v3: Add "today_summary" column to events.db if it doesn't exist
        try:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute(
                    """
                    PRAGMA table_info(events)
                """
                ) as cursor:
                    columns = await cursor.fetchall()
                    column_names = [column[1] for column in columns]
                    if "today_summary" not in column_names:
                        _LOGGER.info(
                            "Migrating events.db to include today_summary column"
                        )
                        await db.execute(
                            """
                            ALTER TABLE events ADD COLUMN today_summary TEXT
                        """
                        )
                        await db.commit()
                        _LOGGER.info("Migration complete")
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error migrating events.db: {e}")

        # v3 -> v4: Migrate image paths to /config/media/llmvision/snapshots from /www/llmvision
        try:
            # Move images to new location
            # Ensure dir exists
            await self.hass.loop.run_in_executor(
                None,
                partial(
                    os.makedirs,
                    self.hass.config.path("media/llmvision/snapshots"),
                    exist_ok=True,
                ),
            )
            src_dir = self.hass.config.path("www/llmvision")
            dst_dir = self.hass.config.path("media/llmvision/snapshots")
            if os.path.exists(src_dir):
                for filename in await self.hass.loop.run_in_executor(
                    None, partial(os.listdir, src_dir)
                ):
                    src_file = os.path.join(src_dir, filename)
                    dst_file = os.path.join(dst_dir, filename)
                    if os.path.isfile(src_file):
                        await self.hass.loop.run_in_executor(
                            None, shutil.move, src_file, dst_file
                        )

            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    UPDATE events SET key_frame = REPLACE(key_frame, '/www/llmvision', '/media/llmvision/snapshots')
                """
                )
                await db.commit()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error migrating image paths in events.db: {e}")

        # v4 -> v4.1: Migrate image paths to /media/llmvision/snapshots from /config/media/llmvision/snapshots
        try:
            # Move images to new location
            # Ensure dir exists
            await self.hass.loop.run_in_executor(
                None,
                partial(
                    os.makedirs,
                    "/media/llmvision/snapshots",
                    exist_ok=True,
                ),
            )
            src_dir = self.hass.config.path("media/llmvision/snapshots")
            dst_dir = "/media/llmvision/snapshots"
            if os.path.exists(src_dir):
                for filename in await self.hass.loop.run_in_executor(
                    None, partial(os.listdir, src_dir)
                ):
                    src_file = os.path.join(src_dir, filename)
                    dst_file = os.path.join(dst_dir, filename)
                    if os.path.isfile(src_file):
                        await self.hass.loop.run_in_executor(
                            None, shutil.move, src_file, dst_file
                        )

            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    UPDATE events SET key_frame = REPLACE(key_frame, '/config/media/llmvision/snapshots', '/media/local/llmvision/snapshots')
                """
                )
                await db.commit()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error migrating image paths in events.db: {e}")

    @property
    def extra_state_attributes(self):
        """Return the state attributes"""
        sorted_events = sorted(
            self._events, key=lambda event: event.start, reverse=True
        )
        # Set limit to 10 newest events to improve performance
        events = sorted_events[:10]
        return {
            "events": [event.summary for event in events],
            "starts": [event.start for event in events],
            "ends": [event.end for event in events],
            "summaries": [event.description for event in events],
            "key_frames": [event.location.split(",")[0] for event in events],
            "camera_names": [
                (
                    event.location.split(",")[1]
                    if len(event.location.split(",")) > 1
                    else ""
                )
                for event in events
            ],
            "today_summary": self._today_summary,
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

    @property
    async def linked_images(self):
        """Returns the filenames of key_frames associated with events"""
        await self.async_update()
        return [
            os.path.basename(event.location.split(",")[0]) for event in self._events
        ]

    async def _initialize_db(self):
        """Initialize database"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        uid TEXT PRIMARY KEY,
                        summary TEXT,
                        start TEXT,
                        end TEXT,
                        description TEXT,
                        key_frame TEXT,
                        camera_name TEXT,
                        today_summary TEXT
                    )
                """
                )
                await db.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_start ON events (start)
                """
                )
                await db.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_end ON events (end)
                """
                )
                await db.commit()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error initializing database: {e}")

    async def async_update(self) -> None:
        """Loads events from database"""
        _LOGGER.debug("Updating calendar events from database")
        await self._initialize_db()

        # calculate the cutoff date for retention
        if self._retention_time is not None and self._retention_time > 0:
            cutoff_date = dt_util.utcnow() - datetime.timedelta(
                days=self._retention_time
            )
            _LOGGER.debug(
                f"Retention time set to {self._retention_time} days, deleting events before {cutoff_date}"
            )
            # find events older than retention time and delete them
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute("SELECT uid, start FROM events") as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        event_uid = row[0]
                        event_start = dt_util.parse_datetime(row[1])
                        if event_start < cutoff_date:
                            _LOGGER.info(
                                f"Deleting event {event_uid} with start {event_start} as it is older than cutoff date {cutoff_date}"
                            )
                            await self.async_delete_event(event_uid)

        # load events
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT * FROM events") as cursor:
                rows = await cursor.fetchall()
                self._events = [
                    CalendarEvent(
                        uid=row[0],
                        summary=row[1],
                        start=dt_util.as_local(dt_util.parse_datetime(row[2])),
                        end=dt_util.as_local(dt_util.parse_datetime(row[3])),
                        description=row[4],
                        location=f"{row[5]},{row[6]}" if row[6] else row[5],
                    )
                    for row in rows
                ]
                self._events.sort(key=lambda event: event.start, reverse=True)
                self._today_summary = rows[-1][7] if rows and len(rows) != 0 else ""

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
        _LOGGER.info(f"Creating event: {kwargs}")
        await self.async_update()
        dtstart = kwargs[EVENT_START]
        dtend = kwargs[EVENT_END]
        start: datetime.datetime
        end: datetime.datetime
        summary = kwargs[EVENT_SUMMARY]
        description = kwargs.get(EVENT_DESCRIPTION)
        key_frame = kwargs.get("key_frame", "")
        camera_name = kwargs.get("camera_name", "")
        today_summary = kwargs.get("today_summary", "")

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
            location=f"{key_frame},{camera_name}",
        )
        await self._insert_event(event, today_summary)

    async def _insert_event(self, event: CalendarEvent, today_summary: str) -> None:
        """Inserts a new event into the database"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                _LOGGER.info(f"Inserting event into database: {event}")
                await db.execute(
                    """
                    INSERT INTO events (uid, summary, start, end, description, key_frame, camera_name, today_summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event.uid,
                        event.summary,
                        dt_util.as_local(
                            self._ensure_datetime(event.start)
                        ).isoformat(),
                        dt_util.as_local(self._ensure_datetime(event.end)).isoformat(),
                        event.description,
                        event.location.split(",")[0],
                        (
                            event.location.split(",")[1]
                            if len(event.location.split(",")) > 1
                            else ""
                        ),
                        today_summary,
                    ),
                )
                await db.commit()
                await self.async_update()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error inserting event into database: {e}")

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Deletes an event from the calendar."""
        _LOGGER.info(f"Deleting event with UID: {uid}")
        await self._delete_image(uid)
        await self._delete_event_from_db(uid)

    async def _delete_event_from_db(self, uid: str) -> None:
        """Deletes an event from the database"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("DELETE FROM events WHERE uid = ?", (uid,))
                await db.commit()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error deleting event from database: {e}")

    async def _delete_image(self, uid: str):
        """Deletes the image associated with the event"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute(
                    "SELECT key_frame FROM events WHERE uid = ?", (uid,)
                ) as cursor:
                    key_frame = await cursor.fetchone()
                    if key_frame:
                        key_frame = key_frame[0]
                        if os.path.exists(key_frame) and f"/{DOMAIN}/" in key_frame:
                            os.remove(key_frame)
                            _LOGGER.info(f"Deleted image: {key_frame}")
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error deleting image: {e}")

    async def _cleanup(self):
        """Deletes images not associated with any events.
        Protects:
          - Images linked to events.
          - Pending key_frames (event insert in progress).
          - Very new files (grace period).
        """
        GRACE_SECONDS = 10

        async with self._cleanup_lock:
            filenames = set(await self.linked_images)
            pending_basenames = {os.path.basename(p) for p in self._pending_key_frames}
            protected = filenames | pending_basenames

            def delete_files(path, protected_names, grace, now_ts):
                removed = 0
                try:
                    for file in os.listdir(path):
                        file_path = os.path.join(path, file)
                        if not os.path.isfile(file_path):
                            continue
                        # Skip protected
                        if file in protected_names:
                            continue
                        # Skip very new files (grace window)
                        try:
                            mtime = os.path.getmtime(file_path)
                            if (now_ts - mtime) < grace:
                                continue
                        except OSError:
                            continue
                        _LOGGER.info(f"[CLEANUP] Removing unlinked snapshot: {file}")
                        try:
                            os.remove(file_path)
                            removed += 1
                        except OSError as e:
                            _LOGGER.warning(
                                f"[CLEANUP] Failed to remove {file_path}: {e}"
                            )
                except FileNotFoundError:
                    return
                if removed:
                    _LOGGER.debug(f"[CLEANUP] Removed {removed} orphaned snapshot(s)")

            now_ts = datetime.datetime.now().timestamp()
            await self.hass.loop.run_in_executor(
                None,
                delete_files,
                self._file_path,
                protected,
                GRACE_SECONDS,
                now_ts,
            )

    async def get_summaries(self, start: datetime, end: datetime):
        """Generates a summary of events between start and end"""
        await self.async_update()
        events = await self.async_get_events(self.hass, start, end)
        events_summaries = "\n".join([event.summary for event in events])
        return events_summaries

    async def remember(
        self, start, end, label, key_frame, summary, camera_name="", today_summary=""
    ):
        """Remembers the event"""
        _LOGGER.info(
            f"(REMEMBER) Adding event: {label} from {start} to {end} with key_frame: {key_frame} and camera_name: {camera_name}"
        )
        # Mark key_frame as pending so cleanup won't remove it before DB insert
        if key_frame:
            self._pending_key_frames.add(key_frame)
        try:
            await self.async_create_event(
                dtstart=start,
                dtend=end,
                summary=label,
                description=summary,
                key_frame=key_frame,
                camera_name=camera_name,
                today_summary=today_summary,
            )
        finally:
            # Remove from pending
            if key_frame:
                self._pending_key_frames.discard(key_frame)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    calendar_entity = Timeline(hass, config_entry)
    async_add_entities([calendar_entity])
