import aiosqlite
import shutil
import datetime
import uuid
import os, re
import json
import asyncio
from .const import DOMAIN, CONF_RETENTION_TIME, CONF_TIMELINE_LANGUAGE
from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from functools import partial
import logging

_LOGGER = logging.getLogger(__name__)

DB_VERSION = 4


async def _get_category_and_label(
    hass: HomeAssistant, config_entry: ConfigEntry, query: str
) -> tuple[str, str]:
    """Return (category, label) for the best match in the query using the language regex template.
    - category: top-level category key (e.g., 'people', 'vehicles', ...)
    - label: canonical label mapped from the matched synonym (e.g., 'person', 'car', ...)
    Returns ("", "") when no match is found.
    """

    def load_lang_json(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Determine language (fallback to 'en')
    language = config_entry.options.get(CONF_TIMELINE_LANGUAGE) or "English"

    lang_map = {
        "Bulgarian": "bg",
        "Catalan": "ca",
        "Czech": "cs",
        "German": "de",
        "English": "en",
        "Spanish": "es",
        "French": "fr",
        "Hungarian": "hu",
        "Italian": "it",
        "Dutch": "nl",
        "Polish": "pl",
        "Portuguese": "pt",
        "Slovak": "sk",
        "Swedish": "sv",
    }
    lang_code = lang_map.get(language, "en")

    # Load language json from /timeline_strings/{language}.json
    lang_file_path = os.path.join(
        os.path.dirname(__file__), "timeline_strings", f"{lang_code}.json"
    )
    if not os.path.exists(lang_file_path):
        _LOGGER.warning(
            f"Language file {lang_file_path} does not exist. Defaulting to English."
        )
        lang_file_path = os.path.join(
            os.path.dirname(__file__), "timeline_strings", "en.json"
        )

    try:
        lang_data = await hass.async_add_executor_job(load_lang_json, lang_file_path)
    except Exception as e:
        _LOGGER.error(f"Error loading language file {lang_file_path}: {e}")
        return ("", "")

    categories_data = lang_data.get("categories", {})
    regex_template = lang_data.get("regex")

    def compile_pattern(key: str):
        """Compile a regex pattern for a given key using the optional template in the JSON.
        Supports:
          - string like: "`\\b${key}s?\\b`, 'i'"
          - object like: {"pattern": "\\b${key}s?\\b", "flags": "i"}
        Falls back to: r"\b{key}s?\b" with IGNORECASE.
        """
        # Defaults
        pattern = rf"\b{re.escape(key)}s?\b"
        flags = re.IGNORECASE

        def flags_from_str(f: str) -> int:
            f = (f or "").lower()
            fl = 0
            if "i" in f:
                fl |= re.IGNORECASE
            if "m" in f:
                fl |= re.MULTILINE
            if "s" in f:
                fl |= re.DOTALL
            # 'u' (unicode) is default in Python 3; no need to set
            return fl

        try:
            if isinstance(regex_template, str):
                # Expect something like: "`\\b${key}s?\\b`, 'i'"
                m = re.search(r"`([^`]*)`(?:\s*,\s*'([a-zA-Z]+)')?", regex_template)
                if m:
                    tpl_pat = m.group(1)
                    tpl_flags = m.group(2) or ""
                    tpl_pat = tpl_pat.replace("${key}", re.escape(key))
                    pattern = tpl_pat
                    flags = flags_from_str(tpl_flags)
            elif isinstance(regex_template, dict):
                tpl_pat = regex_template.get("pattern")
                tpl_flags = regex_template.get("flags", "")
                if isinstance(tpl_pat, str):
                    tpl_pat = tpl_pat.replace("${key}", re.escape(key))
                    pattern = tpl_pat
                    flags = flags_from_str(tpl_flags)
        except Exception as e:
            _LOGGER.debug(f"Failed to apply regex template for key '{key}': {e}")

        try:
            return re.compile(pattern, flags)
        except re.error as e:
            _LOGGER.warning(f"Invalid regex for key '{key}': {pattern} ({e})")
            return None

    # Collect all matches so we can pick the best (longest) one
    matches: list[tuple[int, str, str]] = []  # (key_length, category, label)
    q = query or ""

    for cat_name, cat_def in categories_data.items():
        objects = (cat_def or {}).get("labels", {})
        if not isinstance(objects, dict):
            continue

        for key, canonical in objects.items():
            pat = compile_pattern(str(key))
            if pat and pat.search(q):
                canonical_label = str(canonical) if canonical else str(key)
                matches.append((len(str(key)), str(cat_name), canonical_label))

    if not matches:
        return ("", "")

    # Prefer the longest key match. If tie, preserve original order
    matches.sort(key=lambda x: x[0], reverse=True)
    _, category, label = matches[0]
    return (category, label)


class Event:
    def __init__(
        self,
        uid: str,
        title: str,
        start: datetime.datetime,
        end: datetime.datetime,
        description: str,
        key_frame: str,
        camera_name: str,
        category: str,
        label: str,
    ):
        self.uid = uid
        self.title = title
        self.start = start
        self.end = end
        self.description = description
        self.key_frame = key_frame
        self.camera_name = camera_name
        self.category = category
        self.label = label

    def __repr__(self):
        return f"Event(uid={self.uid}, title={self.title}, start={self.start}, end={self.end}, description={self.description}, key_frame={self.key_frame}, camera_name={self.camera_name}, category={self.category}, label={self.label})"

    def __str__(self):
        return self.__repr__()


class Timeline:
    """Representation of a Calendar."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the calendar"""
        self.hass = hass
        self.events: list[Event] = []
        self.today_summary = ""
        self.retention_time = config_entry.data.get(CONF_RETENTION_TIME)

        # Track key_frame paths whose DB rows are not yet committed
        self._pending_key_frames: set[str] = set()
        self._cleanup_lock = asyncio.Lock()
        self._config_entry = config_entry

        # Path to the JSON file where events are stored
        self._db_path = os.path.join(self.hass.config.path("llmvision"), "events.db")
        self._media_path = f"/media/llmvision/snapshots"
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        os.makedirs(self._media_path, exist_ok=True)

        self.hass.async_create_task(self._initialize_db())
        self.hass.async_create_task(self._migrate())
        self.hass.async_create_task(self.load_events())
        self.hass.async_create_task(self._cleanup())

    async def _get_db_version(self) -> int:
        """Return PRAGMA user_version (0 if unset)."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute("PRAGMA user_version") as cur:
                    row = await cur.fetchone()
                    return int(row[0] or 0)
        except Exception as e:
            _LOGGER.debug(f"Failed to read DB user_version: {e}")
            return 0

    async def _set_db_version(self, version: int) -> None:
        """Set PRAGMA user_version."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(f"PRAGMA user_version = {int(version)}")
                await db.commit()
        except Exception as e:
            _LOGGER.warning(f"Failed to set DB user_version to {version}: {e}")

    async def _has_latest_schema(self) -> bool:
        """Checks if the events table matches the latest schema columns."""
        expected = {
            "uid",
            "title",
            "start",
            "end",
            "description",
            "key_frame",
            "camera_name",
            "category",
            "label",
        }
        try:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute("PRAGMA table_info(events)") as cursor:
                    cols = [r[1] for r in await cursor.fetchall()]
            return expected.issubset(set(cols))
        except Exception as e:
            _LOGGER.debug(f"Failed to inspect DB schema: {e}")
            return False

    async def _initialize_db(self):
        """Initialize database"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        uid TEXT PRIMARY KEY,
                        title TEXT,
                        start TEXT,
                        end TEXT,
                        description TEXT,
                        key_frame TEXT,
                        camera_name TEXT,
                        category TEXT,
                        label TEXT
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
        # If version is unset (0), but schema already matches latest, set it
        try:
            current = await self._get_db_version()
            if current == 0 and await self._has_latest_schema():
                await self._set_db_version(DB_VERSION)
                _LOGGER.debug(
                    f"Initialized DB user_version to {DB_VERSION} (schema up-to-date)"
                )
        except Exception as e:
            _LOGGER.debug(f"Post-init version set skipped: {e}")

    async def _migrate(self):
        """Handles migration for events.db (current v4)"""
        current_version = await self._get_db_version()
        if current_version >= DB_VERSION:
            return

        _LOGGER.info(
            f"Starting DB migration (user_version={current_version} -> {DB_VERSION})"
        )
        # v1 -> v2: Migrate events from events.json to events.db
        old_db_path = os.path.join(self.hass.config.path("llmvision"), "events.json")
        if os.path.exists(old_db_path):
            _LOGGER.info("Migrating events from events.json to events.db")
            with open(old_db_path, "r") as file:
                data = json.load(file)
                event_counter = 0
                for event in data:
                    await self.hass.loop.create_task(
                        self.create_event(
                            dtstart=datetime.datetime.fromisoformat(event["start"]),
                            dtend=datetime.datetime.fromisoformat(event["end"]),
                            summary=event["summary"],
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
            _LOGGER.error(f"Error migrating events.db to v4: {e}")

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
            _LOGGER.error(f"Error migrating events.db to v4.1: {e}")

        # v4.1 -> v4.2: Add category column to events.db
        try:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute("""PRAGMA table_info(events)""") as cursor:
                    columns = await cursor.fetchall()
                    column_names = [column[1] for column in columns]
                    if "category" not in column_names:
                        _LOGGER.info("Migrating events.db to include category column")
                        await db.execute(
                            """ALTER TABLE events ADD COLUMN category TEXT"""
                        )
                        await db.commit()
                        _LOGGER.info("Timeline DB migration to v4.2 complete")
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error migrating events.db to v4.2: {e}")

        # v4.2 -> v4.3: Remove today_summary column from events.db, add label column, populate label column, rename summary->title
        try:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute("""PRAGMA table_info(events)""") as cursor:
                    columns = await cursor.fetchall()
                    column_names = [column[1] for column in columns]
                    if "today_summary" in column_names:
                        _LOGGER.info("Removing today_summary column from events.db")
                        await db.execute(
                            """ALTER TABLE events DROP COLUMN today_summary"""
                        )
                        await db.commit()
                    if "label" not in column_names:
                        _LOGGER.info("Adding label column to events.db")
                        await db.execute("""ALTER TABLE events ADD COLUMN label TEXT""")
                        await db.commit()
                    if "summary" in column_names:
                        _LOGGER.info("Renaming summary column to title")
                        await db.execute("""ALTER TABLE events RENAME TO events_old""")
                        await db.execute(
                            """
                            CREATE TABLE events (
                                uid TEXT PRIMARY KEY,
                                title TEXT,
                                start TEXT,
                                end TEXT,
                                description TEXT,
                                key_frame TEXT,
                                camera_name TEXT,
                                category TEXT,
                                label TEXT
                            )
                        """
                        )
                        await db.execute(
                            """
                            INSERT INTO events (uid, title, start, end, description, key_frame, camera_name, category, label)
                            SELECT uid, summary, start, end, description, key_frame, camera_name, category, label
                            FROM events_old
                        """
                        )
                        await db.execute("""DROP TABLE events_old""")
                        await db.commit()
                        _LOGGER.info("Renamed summary column to title")
                    if "label" in column_names:
                        _LOGGER.info(
                            "Populating label and category columns in events.db"
                        )
                        async with db.execute(
                            """SELECT uid, title FROM events WHERE label IS NULL OR label = '' OR category IS NULL OR category = ''"""
                        ) as cursor:
                            rows = await cursor.fetchall()
                            for row in rows:
                                uid = row[0]
                                title = row[1]
                                (category, label) = await _get_category_and_label(
                                    self.hass, self._config_entry, title
                                )
                                await db.execute(
                                    """UPDATE events SET label = ? WHERE uid = ?""",
                                    (label, uid),
                                )
                                await db.execute(
                                    """UPDATE events SET category = ? WHERE uid = ?""",
                                    (category, uid),
                                )
                        await db.commit()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error migrating events.db to v4.3: {e}")

        # Mark migration complete by setting user_version
        await self._set_db_version(DB_VERSION)
        _LOGGER.info(f"DB migration complete (user_version={DB_VERSION})")

    def _ensure_datetime(self, dt):
        """Ensures the input is a datetime.datetime object"""
        if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
            dt = datetime.datetime.combine(dt, datetime.datetime.min.time())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt

    async def get_linked_images(self):
        """Returns the filenames of key_frames associated with events"""
        await self.load_events()
        return [
            os.path.basename(e.key_frame)
            for e in self.events
            if getattr(e, "key_frame", None)
        ]

    async def load_events(self):
        """Loads events from the database into memory"""
        self.events = []
        try:
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute(
                    """
                    SELECT
                        uid, title, start, end, description,
                        category, key_frame, camera_name, label
                    FROM events
                    """
                ) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        # row: uid, summary, start, end, description, category, key_frame, camera_name, label
                        try:
                            row_start = (
                                dt_util.parse_datetime(row[2]) if row[2] else None
                            )
                            row_end = dt_util.parse_datetime(row[3]) if row[3] else None
                        except Exception:
                            # skip malformed rows
                            continue

                        if row_start:
                            row_start = self._ensure_datetime(row_start)
                        if row_end:
                            row_end = self._ensure_datetime(row_end)

                        event = Event(
                            uid=row[0],
                            title=row[1],
                            start=row_start,
                            end=row_end,
                            description=row[4],
                            category=row[5],
                            key_frame=row[6],
                            camera_name=row[7],
                            label=row[8],
                        )
                        self.events.append(event)
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error loading events from database: {e}")

    async def get_all_events(self) -> list[Event]:
        """Returns calendar events"""
        return self.events

    async def get_events_json(
        self, limit=100, cameras=[], categories=[], start=None, end=None
    ) -> list[dict]:
        """Returns json event data from the database. Used by the API.
        Supports filtering by camera, start/end range and sorting by start (newest first).
        category are ignored for now.
        """
        events: list[dict] = []

        # Normalize start/end inputs to timezone-aware datetimes (or None)
        def normalize_input_dt(dt_in):
            if dt_in is None:
                return None
            try:
                if isinstance(dt_in, str):
                    dt = dt_util.parse_datetime(dt_in)
                else:
                    dt = dt_in
                return self._ensure_datetime(dt)
            except Exception:
                return None

        start_dt = normalize_input_dt(start)
        end_dt = normalize_input_dt(end)

        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                """
                SELECT
                    uid, title, start, end, description,
                    category, key_frame, camera_name, label
                FROM events
                """
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    # row: uid, title, start, end, description, key_frame, camera_name, label
                    try:
                        row_start = dt_util.parse_datetime(row[2]) if row[2] else None
                        row_end = dt_util.parse_datetime(row[3]) if row[3] else None
                    except Exception:
                        # skip malformed rows
                        continue

                    if row_start:
                        row_start = self._ensure_datetime(row_start)
                    if row_end:
                        row_end = self._ensure_datetime(row_end)

                    # Camera filter
                    if cameras:
                        camera_name = (row[7] or "").lower()
                        if camera_name not in [c.lower() for c in cameras]:
                            continue

                    # Category filter
                    if categories:
                        category_name = (row[5] or "").lower()
                        if category_name not in [c.lower() for c in categories]:
                            continue

                    # Range overlap filter
                    if start_dt and row_end and row_end <= start_dt:
                        continue
                    if end_dt and row_start and row_start >= end_dt:
                        continue

                    events.append(
                        {
                            "uid": row[0],
                            "title": row[1],
                            "start": row[2],
                            "end": row[3],
                            "description": row[4],
                            "key_frame": row[6],
                            "camera_name": row[7],
                            "category": row[5],
                            "label": row[8],
                        }
                    )

        # Sort by start datetime descending (newest first). Malformed/missing start go to the end.
        def sort_key(ev):
            try:
                d = dt_util.parse_datetime(ev.get("start"))
                return dt_util.as_local(self._ensure_datetime(d))
            except Exception:
                return datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)

        events.sort(key=sort_key, reverse=True)

        if limit is not None:
            return events[:limit]

        return events

    async def create_event(
        self,
        start: datetime.datetime,
        end: datetime.datetime,
        title: str,
        description: str,
        key_frame: str,
        camera_name: str,
        category: str = "",
        label: str = "",
    ) -> None:
        """Adds a new event to calendar"""
        await self.load_events()

        # Ensure dtstart and dtend are datetime objects
        if isinstance(start, str):
            start = datetime.datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.datetime.fromisoformat(end)

        start = dt_util.as_local(start)
        end = dt_util.as_local(end)

        # Resolve category and label if not provided
        if not label or not category:
            try:
                (auto_category, auto_label) = await _get_category_and_label(
                    self.hass, self._config_entry, label
                )
                if not category:
                    category = auto_category
                if not label:
                    label = auto_label
            except Exception as e:
                _LOGGER.warning(f"Failed to resolve category: {e}")

        # Mark key_frame as pending so cleanup won't remove it before DB insert
        pending_name = None
        if key_frame:
            pending_name = (os.path.basename(key_frame) or "").lower()
            self._pending_key_frames.add(pending_name)
        try:
            event = Event(
                uid=str(uuid.uuid4()),
                title=title,
                start=start,
                end=end,
                description=description,
                key_frame=key_frame,
                camera_name=camera_name,
                category=category,
                label=label,
            )
            _LOGGER.info(f"Creating event: {event}")
            await self._insert_event(event)
        finally:
            # Remove from pending once DB insert is done
            if pending_name:
                self._pending_key_frames.discard(pending_name)

    async def _insert_event(self, event: Event) -> None:
        """Inserts a new event into the database"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                _LOGGER.info(f"Inserting event into database: {event}")
                await db.execute(
                    """
                    INSERT INTO events (uid, title, start, end, description, key_frame, camera_name, category, label)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        event.uid,
                        event.title,
                        dt_util.as_local(
                            self._ensure_datetime(event.start)
                        ).isoformat(),
                        dt_util.as_local(self._ensure_datetime(event.end)).isoformat(),
                        event.description,
                        event.key_frame,
                        event.camera_name,
                        event.category,
                        event.label,
                    ),
                )
                await db.commit()
                await self.load_events()
        except aiosqlite.Error as e:
            _LOGGER.error(f"Error inserting event into database: {e}")

    async def delete_event(
        self,
        uid: str,
    ) -> bool:
        """Deletes an event from the calendar."""
        _LOGGER.info(f"Deleting event with UID: {uid}")

        async def _delete_event_from_db(uid: str) -> bool:
            """Deletes an event from the database"""
            try:
                async with aiosqlite.connect(self._db_path) as db:
                    await db.execute("DELETE FROM events WHERE uid = ?", (uid,))
                    await db.commit()
            except aiosqlite.Error as e:
                _LOGGER.error(f"Error deleting event from database: {e}")
                return False
            return True

        async def _delete_image(uid: str) -> bool:
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
                return False
            return True

        success_image = await _delete_image(uid)
        success_event = await _delete_event_from_db(uid)
        return success_image and success_event

    async def _cleanup(self):
        """Deletes images not associated with any events.
        Protects:
          - Images linked to events.
          - Pending key_frames (event insert in progress).
          - Very new files (grace period).
        """
        GRACE_SECONDS = 10

        async with self._cleanup_lock:
            linked_frames = {
                (os.path.basename(n) or "").lower()
                for n in await self.get_linked_images()
            }

        # List files in snapshots dir (in executor, non-blocking)
        try:
            files = await self.hass.async_add_executor_job(os.listdir, self._media_path)
        except FileNotFoundError:
            return

        now_ts = datetime.datetime.now().timestamp()
        removed = 0

        for file in files:
            file_path = os.path.join(self._media_path, file)
            is_file = await self.hass.async_add_executor_job(os.path.isfile, file_path)
            if not is_file:
                continue

            base = (file or "").lower()

            # Protect if linked to an event or pending
            if base in linked_frames or base in self._protected_frames:
                continue

            # Protect new files (grace window)
            try:
                mtime = await self.hass.async_add_executor_job(
                    os.path.getmtime, file_path
                )
                if (now_ts - mtime) < GRACE_SECONDS:
                    continue
            except OSError:
                continue

            _LOGGER.info(f"[CLEANUP] Removing unlinked snapshot: {file}")
            try:
                await self.hass.async_add_executor_job(os.remove, file_path)
                removed += 1
            except OSError as e:
                _LOGGER.warning(f"[CLEANUP] Failed to remove {file_path}: {e}")

        if removed:
            _LOGGER.debug(f"[CLEANUP] Removed {removed} orphaned snapshot(s)")
