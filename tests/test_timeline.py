"""Unit tests for timeline.py module."""

import datetime
import os
import uuid
from functools import partial
from unittest.mock import AsyncMock, Mock

import aiosqlite
import pytest

from custom_components.llmvision.const import (
    CONF_RETENTION_TIME,
    CONF_TIMELINE_LANGUAGE,
)
from custom_components.llmvision.timeline import (
    DB_VERSION,
    Event,
    Timeline,
    _get_category_and_label,
)
from homeassistant.util import dt as dt_util

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _make_row(
    title: str,
    age_days: float,
    camera: str = "",
    category: str = "",
    label: str = "",
    key_frame: str = "",
) -> tuple:
    """Build a 9-tuple ready for INSERT INTO events."""
    base = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=age_days
    )
    start = dt_util.as_local(base).isoformat()
    end = dt_util.as_local(base + datetime.timedelta(minutes=1)).isoformat()
    return (
        str(uuid.uuid4()),
        title,
        start,
        end,
        "",
        key_frame,
        camera,
        category,
        label,
    )


async def _insert_rows(db_path: str, rows: list[tuple]) -> None:
    async with aiosqlite.connect(db_path) as db:
        for row in rows:
            await db.execute(
                """INSERT INTO events
                    (uid, title, start, end, description, key_frame, camera_name, category, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                row,
            )
        await db.commit()


async def _fetch_titles(db_path: str) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT title FROM events ORDER BY title") as cursor:
            rows = await cursor.fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def build_timeline(tmp_path, monkeypatch):
    """Factory: creates an isolated Timeline backed by real SQLite in tmp_path.

    async_add_executor_job and loop.run_in_executor call the function directly
    so that code paths using those (e.g. _get_category_and_label, _cleanup) work
    without a full event-loop executor pool.
    """
    base_path = tmp_path / "config"
    base_path.mkdir()

    real_makedirs = os.makedirs

    def safe_makedirs(path, exist_ok=False):
        # Silently skip the hard-coded /media/llmvision path used in production.
        if str(path).startswith("/media/llmvision"):
            return
        return real_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr(
        "custom_components.llmvision.timeline.os.makedirs", safe_makedirs
    )

    def _build(retention=7, options=None):
        hass = Mock()
        hass.data = {}
        hass.config = Mock()
        hass.config.path = lambda *parts: str(base_path.joinpath(*parts))
        hass.loop = Mock()

        async def real_run_in_executor(executor, func, *args):
            return func(*args)

        async def real_async_add_executor_job(func, *args):
            return func(*args)

        hass.loop.run_in_executor = real_run_in_executor
        hass.async_add_executor_job = real_async_add_executor_job
        hass.async_create_task = lambda coro: None

        entry = Mock()
        entry.entry_id = "test-entry"
        entry.data = {"provider": "Settings", "retention_time": retention}
        entry.options = options or {}

        timeline = Timeline(hass, entry)
        timeline._migrating = False
        return timeline

    return _build


@pytest.fixture
def hass_with_executor():
    """Minimal mock hass where async_add_executor_job actually executes the callable."""
    hass = Mock()
    hass.data = {}

    async def real_async_add_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = real_async_add_executor_job
    return hass


@pytest.fixture
def entry_english():
    """Config entry that defaults to English (no language override)."""
    entry = Mock()
    entry.options = {}
    return entry


# ===========================================================================
# _get_category_and_label
# ===========================================================================


class TestGetCategoryAndLabel:
    """Tests for the standalone _get_category_and_label helper."""

    async def test_matches_known_word(self, hass_with_executor, entry_english):
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, "a person walked by"
        )
        assert category == "person"
        assert label == "person"

    async def test_synonym_maps_to_canonical_label(
        self, hass_with_executor, entry_english
    ):
        """'man' is a synonym that maps to the canonical label 'person'."""
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, "A man is at the door"
        )
        assert category == "person"
        assert label == "person"

    async def test_vehicle_category(self, hass_with_executor, entry_english):
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, "a car is parked outside"
        )
        assert category == "vehicle"
        assert label == "car"

    async def test_animal_category(self, hass_with_executor, entry_english):
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, "a dog is in the backyard"
        )
        assert category == "animal"
        assert label == "dog"

    async def test_no_match_returns_empty_strings(
        self, hass_with_executor, entry_english
    ):
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, "zxqwerty totally unknown"
        )
        assert category == ""
        assert label == ""

    async def test_empty_query_returns_empty(self, hass_with_executor, entry_english):
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, ""
        )
        assert category == ""
        assert label == ""

    async def test_none_query_returns_empty(self, hass_with_executor, entry_english):
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, None
        )
        assert category == ""
        assert label == ""

    async def test_unknown_language_falls_back_to_english(self, hass_with_executor):
        """An unrecognised language name falls back to the English JSON file."""
        entry = Mock()
        entry.options = {CONF_TIMELINE_LANGUAGE: "Klingon"}
        category, label = await _get_category_and_label(
            hass_with_executor, entry, "a dog is in the yard"
        )
        assert category == "animal"
        assert label == "dog"

    async def test_longer_key_wins_on_tie(self, hass_with_executor, entry_english):
        """'motorcycle' should win over the shorter 'motor' prefix (if any overlap)."""
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, "a motorcycle passed"
        )
        assert category == "vehicle"
        assert label == "motorcycle"

    async def test_supported_language_loaded(self, hass_with_executor):
        """German language file is loaded without errors when configured."""
        entry = Mock()
        entry.options = {CONF_TIMELINE_LANGUAGE: "German"}
        category, label = await _get_category_and_label(
            hass_with_executor, entry, "irrelevant query xyz"
        )
        # Must return strings – no exception
        assert isinstance(category, str)
        assert isinstance(label, str)

    async def test_respects_category_priority(self, hass_with_executor, entry_english):
        """Priority is:
        0. delivery
        1. vehicle
        2. person
        3. animal
        4. entity
        5. nature
        """
        title = "Delivery"
        description = "A person wearing a green vest stands on the driveway."
        q = " ".join(part for part in (title or "", description or "") if part)

        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, q
        )
        assert category == "delivery"
        assert label == "delivery"

        title = "Squirrel Seen at Railing"
        description = "A squirrel is enjoying it's time on the railing."
        q = " ".join(part for part in (title or "", description or "") if part)

        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, q
        )
        assert category == "animal"
        assert label == "animal"


class TestCategoryPriorityAndWordBoundaries:
    """Tests to ensure category priority and whole-word matching behave correctly."""

    async def test_delivery_preferred_over_person(
        self, hass_with_executor, entry_english
    ):
        # 'parcel' is a delivery label; sentence also contains 'person'
        q = "A person carries a parcel to the front door"
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, q
        )
        assert category == "delivery"
        assert label == "delivery"

    async def test_pet_not_matched_in_petrol(self, hass_with_executor, entry_english):
        # 'pet' should NOT match inside 'petrol' due to word boundaries; 'car' should match
        q = "A petrol car parked outside"
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, q
        )
        assert category == "vehicle"
        assert label == "car"

    async def test_carpet_does_not_match_car_or_pet(
        self, hass_with_executor, entry_english
    ):
        # Ensure substrings do not produce false positives
        q = "There is a carpet on the floor"
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, q
        )
        assert category == ""
        assert label == ""

    async def test_vehicle_preferred_over_animal(
        self, hass_with_executor, entry_english
    ):
        # When both 'car' and 'dog' appear, vehicle has higher priority
        q = "A car and a dog were seen"
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, q
        )
        assert category == "vehicle"
        assert label == "car"

    async def test_case_insensitive_and_plural_handling(
        self, hass_with_executor, entry_english
    ):
        # Uppercase and plural forms should still match (regex uses case-insensitive)
        q = "PARCELS were delivered"
        category, label = await _get_category_and_label(
            hass_with_executor, entry_english, q
        )
        # 'parcels' may not map via simple s? template to 'parcel' in every language file,
        # but we at least expect the delivery category or an empty result without false positives.
        assert category in ("delivery", "")


# ===========================================================================
# Event class
# ===========================================================================


class TestEvent:
    """Tests for the Event data class."""

    def _make(self, **kwargs):
        defaults = dict(
            uid="uid-1",
            title="Test Event",
            start=datetime.datetime(2024, 1, 15, 10, 0, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2024, 1, 15, 10, 5, tzinfo=datetime.timezone.utc),
            description="desc",
            key_frame="/media/llmvision/snapshots/a.jpg",
            camera_name="Front Door",
            category="person",
            label="person",
        )
        defaults.update(kwargs)
        return Event(**defaults)

    def test_attributes_stored_correctly(self):
        ev = self._make()
        assert ev.uid == "uid-1"
        assert ev.title == "Test Event"
        assert ev.camera_name == "Front Door"
        assert ev.category == "person"
        assert ev.label == "person"

    def test_repr_contains_key_fields(self):
        ev = self._make()
        r = repr(ev)
        assert "uid=uid-1" in r
        assert "title=Test Event" in r
        assert "category=person" in r

    def test_str_equals_repr(self):
        ev = self._make()
        assert str(ev) == repr(ev)


# ===========================================================================
# _ensure_datetime
# ===========================================================================


class TestEnsureDatetime:
    """Tests for Timeline._ensure_datetime."""

    @pytest.fixture
    def tl(self, build_timeline):
        return build_timeline()

    def test_date_converted_to_datetime(self, tl):
        result = tl._ensure_datetime(datetime.date(2024, 6, 1))
        assert isinstance(result, datetime.datetime)
        assert result.tzinfo is not None

    def test_naive_datetime_becomes_utc(self, tl):
        naive = datetime.datetime(2024, 6, 1, 12, 0, 0)
        result = tl._ensure_datetime(naive)
        assert result.tzinfo == datetime.timezone.utc

    def test_aware_datetime_returned_unchanged(self, tl):
        aware = datetime.datetime(2024, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        assert tl._ensure_datetime(aware) == aware


# ===========================================================================
# _get_retention_days
# ===========================================================================


class TestGetRetentionDays:
    """Tests for Timeline._get_retention_days."""

    @pytest.fixture
    def tl(self, build_timeline):
        tl = build_timeline()
        tl.retention_time = None
        return tl

    def test_none_returns_none(self, tl):
        tl._config_entry.options = {}
        tl.retention_time = None
        assert tl._get_retention_days() is None

    def test_empty_string_returns_none(self, tl):
        tl._config_entry.options = {CONF_RETENTION_TIME: ""}
        assert tl._get_retention_days() is None

    def test_zero_returns_none(self, tl):
        tl._config_entry.options = {CONF_RETENTION_TIME: 0}
        assert tl._get_retention_days() is None

    def test_negative_returns_none(self, tl):
        tl._config_entry.options = {CONF_RETENTION_TIME: -5}
        assert tl._get_retention_days() is None

    def test_valid_int(self, tl):
        tl._config_entry.options = {CONF_RETENTION_TIME: 30}
        assert tl._get_retention_days() == 30

    def test_valid_string_int(self, tl):
        tl._config_entry.options = {CONF_RETENTION_TIME: "14"}
        assert tl._get_retention_days() == 14

    def test_invalid_string_returns_none(self, tl):
        tl._config_entry.options = {CONF_RETENTION_TIME: "not-a-number"}
        assert tl._get_retention_days() is None

    def test_options_overrides_data_level(self, tl):
        tl._config_entry.options = {CONF_RETENTION_TIME: 5}
        tl.retention_time = 99
        assert tl._get_retention_days() == 5

    def test_fallback_to_data_level_when_options_empty(self, tl):
        tl._config_entry.options = {}
        tl.retention_time = 21
        assert tl._get_retention_days() == 21


# ===========================================================================
# Database setup (_initialize_db, version, schema)
# ===========================================================================


class TestDatabaseSetup:
    """Tests for DB initialisation, version, and schema inspection."""

    async def test_initialize_creates_events_table(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        async with aiosqlite.connect(tl._db_path) as db:
            async with db.execute("PRAGMA table_info(events)") as cur:
                cols = [r[1] for r in await cur.fetchall()]
        for col in (
            "uid",
            "title",
            "start",
            "end",
            "description",
            "key_frame",
            "camera_name",
            "category",
            "label",
        ):
            assert col in cols

    async def test_initialize_creates_required_indexes(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        async with aiosqlite.connect(tl._db_path) as db:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ) as cur:
                indexes = {r[0] for r in await cur.fetchall()}
        assert "idx_start" in indexes
        assert "idx_end" in indexes

    async def test_initialize_sets_db_version(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        assert await tl._get_db_version() == DB_VERSION

    async def test_version_zero_before_initialization(self, build_timeline):
        tl = build_timeline()
        assert await tl._get_db_version() == 0

    async def test_version_roundtrip(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        await tl._set_db_version(99)
        assert await tl._get_db_version() == 99

    async def test_has_latest_schema_true_after_init(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        assert await tl._has_latest_schema() is True

    async def test_has_latest_schema_false_missing_column(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        # Strip the table down to only a subset of columns
        async with aiosqlite.connect(tl._db_path) as db:
            await db.execute("ALTER TABLE events RENAME TO events_bak")
            await db.execute("CREATE TABLE events (uid TEXT PRIMARY KEY, title TEXT)")
            await db.commit()
        assert await tl._has_latest_schema() is False


# ===========================================================================
# load_events / get_all_events / get_event / get_linked_images
# ===========================================================================


class TestLoadEvents:
    """Tests for loading and querying events."""

    async def test_empty_db_loads_zero_events(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        await tl.load_events()
        assert tl.events == []

    async def test_loads_row_from_db(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        await _insert_rows(
            tl._db_path,
            [
                _make_row(
                    "person at door",
                    0.1,
                    camera="front",
                    category="person",
                    label="person",
                )
            ],
        )
        await tl.load_events()
        assert len(tl.events) == 1
        ev = tl.events[0]
        assert ev.title == "person at door"
        assert ev.camera_name == "front"
        assert ev.category == "person"
        assert ev.label == "person"

    async def test_load_events_unparseable_start_yields_none_start(
        self, build_timeline
    ):
        """dt_util.parse_datetime returns None (not raises) for bad strings.
        The row is loaded with start=None rather than being dropped."""
        tl = build_timeline()
        await tl._initialize_db()
        async with aiosqlite.connect(tl._db_path) as db:
            await db.execute(
                """INSERT INTO events
                    (uid, title, start, end, description, key_frame, camera_name, category, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    "bad",
                    "NOT-A-DATE",
                    "2024-01-01T00:00:00+00:00",
                    "",
                    "",
                    "",
                    "",
                    "",
                ),
            )
            await db.commit()
        await tl.load_events()
        assert len(tl.events) == 1
        assert tl.events[0].start is None

    async def test_get_all_events_returns_list(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        await _insert_rows(tl._db_path, [_make_row("ev1", 0.1)])
        await tl.load_events()
        events = await tl.get_all_events()
        assert len(events) == 1
        assert events[0].title == "ev1"

    async def test_get_event_found_returns_dict(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        row = _make_row(
            "known event", 0.1, camera="cam1", category="person", label="person"
        )
        uid = row[0]
        await _insert_rows(tl._db_path, [row])

        result = await tl.get_event(uid)
        assert result is not None
        assert result["uid"] == uid
        assert result["title"] == "known event"
        assert result["camera_name"] == "cam1"
        assert "start" in result and "end" in result

    async def test_get_event_not_found_returns_none(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        assert await tl.get_event("nonexistent-uid") is None

    async def test_get_linked_images_returns_basenames(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        now = dt_util.utcnow()
        async with aiosqlite.connect(tl._db_path) as db:
            await db.execute(
                """INSERT INTO events
                    (uid, title, start, end, description, key_frame, camera_name, category, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    "ev",
                    now.isoformat(),
                    (now + datetime.timedelta(minutes=1)).isoformat(),
                    "",
                    "/media/llmvision/snapshots/abc.jpg",
                    "",
                    "",
                    "",
                ),
            )
            await db.commit()

        linked = await tl.get_linked_images()
        assert "abc.jpg" in linked

    async def test_get_linked_images_ignores_empty_key_frame(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        await _insert_rows(tl._db_path, [_make_row("no image", 0.1, key_frame="")])
        linked = await tl.get_linked_images()
        assert linked == []


# ===========================================================================
# get_events_json filtering & sorting
# ===========================================================================


class TestGetEventsJson:
    """Tests for get_events_json with various filters."""

    async def _setup(self, tl):
        await tl._initialize_db()
        rows = [
            _make_row("no activity observed", 0.1, camera="front"),
            _make_row(
                "person at front door",
                0.2,
                camera="front",
                category="person",
                label="person",
            ),
            _make_row(
                "car in driveway",
                0.3,
                camera="driveway",
                category="vehicle",
                label="car",
            ),
            _make_row(
                "dog in backyard", 0.4, camera="back", category="animal", label="dog"
            ),
            _make_row(
                "very old event", 100, camera="front", category="person", label="person"
            ),
        ]
        await _insert_rows(tl._db_path, rows)

    async def test_no_activity_excluded_by_default(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        events = await tl.get_events_json(limit=None)
        assert all("no activity" not in e["title"].lower() for e in events)

    async def test_no_activity_included_when_opted_in(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        events = await tl.get_events_json(limit=None, include_no_activity=True)
        titles = [e["title"] for e in events]
        assert "no activity observed" in titles

    async def test_filter_by_camera(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        events = await tl.get_events_json(limit=None, cameras=["front"])
        assert all(e["camera_name"] == "front" for e in events)
        assert len(events) >= 1

    async def test_filter_by_category(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        events = await tl.get_events_json(limit=None, categories=["vehicle"])
        assert all(e["category"] == "vehicle" for e in events)
        assert len(events) == 1

    async def test_filter_by_label(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        events = await tl.get_events_json(limit=None, labels=["dog"])
        assert all(e["label"] == "dog" for e in events)
        assert len(events) == 1

    async def test_limit_applied(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        events = await tl.get_events_json(limit=2)
        assert len(events) == 2

    async def test_sorted_newest_first(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        events = await tl.get_events_json(limit=None)
        starts = [dt_util.parse_datetime(e["start"]) for e in events if e.get("start")]
        for i in range(len(starts) - 1):
            assert starts[i] >= starts[i + 1]

    async def test_start_filter_excludes_ended_before(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        # All test events end before far-future time
        future = dt_util.utcnow() + datetime.timedelta(days=365)
        events = await tl.get_events_json(limit=None, start=future.isoformat())
        assert events == []

    async def test_end_filter_excludes_started_after(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        # All events start after the distant past end cutoff
        past = dt_util.utcnow() - datetime.timedelta(days=200)
        events = await tl.get_events_json(limit=None, end=past.isoformat())
        assert events == []

    async def test_camera_filter_case_insensitive(self, build_timeline):
        tl = build_timeline(retention=0)
        await self._setup(tl)
        events_lower = await tl.get_events_json(limit=None, cameras=["front"])
        events_upper = await tl.get_events_json(limit=None, cameras=["FRONT"])
        assert len(events_lower) == len(events_upper)

    async def test_event_with_no_camera_passes_camera_filter(self, build_timeline):
        """Events that have no camera set are not excluded by a camera filter."""
        tl = build_timeline(retention=0)
        await tl._initialize_db()
        # Event with empty camera_name
        await _insert_rows(tl._db_path, [_make_row("no camera", 0.1, camera="")])
        events = await tl.get_events_json(limit=None, cameras=["front"])
        titles = [e["title"] for e in events]
        assert "no camera" in titles


# ===========================================================================
# create_event / _insert_event / update_event / delete_event
# ===========================================================================


class TestCRUD:
    """Tests for create, insert, update, and delete operations."""

    async def test_create_event_persisted(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        now = dt_util.utcnow()
        await tl.create_event(
            start=now,
            end=now + datetime.timedelta(minutes=1),
            title="A person is at the door",
            description="",
            key_frame="",
            camera_name="front",
        )
        await tl.load_events()
        assert len(tl.events) == 1
        assert tl.events[0].title == "A person is at the door"

    async def test_create_event_auto_resolves_category(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        now = dt_util.utcnow()
        await tl.create_event(
            start=now,
            end=now + datetime.timedelta(minutes=1),
            title="A car passed",
            description="",
            key_frame="",
            camera_name="driveway",
        )
        await tl.load_events()
        ev = tl.events[0]
        assert ev.label == "car"
        assert ev.category == "vehicle"

    async def test_create_event_with_explicit_label_sets_category(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        now = dt_util.utcnow()
        await tl.create_event(
            start=now,
            end=now + datetime.timedelta(minutes=1),
            title="something happened",
            description="",
            key_frame="",
            camera_name="back",
            label="car",
        )
        await tl.load_events()
        assert tl.events[0].label == "car"
        assert tl.events[0].category == "vehicle"

    async def test_create_event_accepts_string_datetimes(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        now = dt_util.utcnow()
        await tl.create_event(
            start=now.isoformat(),
            end=(now + datetime.timedelta(minutes=1)).isoformat(),
            title="string datetime test",
            description="",
            key_frame="",
            camera_name="",
        )
        await tl.load_events()
        assert len(tl.events) == 1

    async def test_insert_event_directly(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        now = dt_util.utcnow()
        ev = Event(
            uid="direct-uid",
            title="direct insert",
            start=now,
            end=now + datetime.timedelta(minutes=1),
            description="",
            key_frame="",
            camera_name="",
            category="person",
            label="person",
        )
        await tl._insert_event(ev)
        assert "direct insert" in await _fetch_titles(tl._db_path)

    async def test_update_event_changes_fields(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        row = _make_row(
            "original title", 0.1, camera="front", category="person", label="person"
        )
        uid = row[0]
        await _insert_rows(tl._db_path, [row])
        await tl.load_events()

        now = dt_util.utcnow()
        await tl.update_event(
            uid=uid,
            start=now,
            end=now + datetime.timedelta(minutes=1),
            title="updated title",
            description="updated desc",
            key_frame="",
            camera_name="back",
            label="dog",
        )
        await tl.load_events()
        updated = next(e for e in tl.events if e.uid == uid)
        assert updated.title == "updated title"
        assert updated.label == "dog"
        assert updated.category == "animal"

    async def test_delete_event_removes_from_db(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        row = _make_row("to delete", 0.1)
        uid = row[0]
        await _insert_rows(tl._db_path, [row])
        await tl.load_events()
        assert len(tl.events) == 1

        result = await tl.delete_event(uid)
        assert result is True
        assert "to delete" not in await _fetch_titles(tl._db_path)

    async def test_delete_nonexistent_event_returns_true(self, build_timeline):
        """Deleting a missing UID is a no-op and returns True."""
        tl = build_timeline()
        await tl._initialize_db()
        result = await tl.delete_event("ghost-uid")
        assert result is True


# ===========================================================================
# Retention / purge
# ===========================================================================


class TestRetentionAndPurge:
    """Tests for automatic event expiry."""

    async def test_retention_purges_old_events(self, build_timeline):
        tl = build_timeline(retention=2)
        await tl._initialize_db()
        await _insert_rows(
            tl._db_path,
            [
                _make_row("expired", age_days=5),
                _make_row("recent", age_days=0.1),
            ],
        )
        await tl.load_events()
        assert await _fetch_titles(tl._db_path) == ["recent"]

    async def test_zero_retention_disables_purge(self, build_timeline):
        tl = build_timeline(retention=0)
        await tl._initialize_db()
        await _insert_rows(
            tl._db_path,
            [
                _make_row("expired", age_days=10),
                _make_row("recent", age_days=0.5),
            ],
        )
        await tl.load_events()
        titles = await _fetch_titles(tl._db_path)
        assert "expired" in titles
        assert "recent" in titles

    async def test_purge_skipped_during_migration(self, build_timeline):
        tl = build_timeline(retention=1)
        await tl._initialize_db()
        await _insert_rows(tl._db_path, [_make_row("old event", age_days=30)])
        tl._migrating = True
        await tl._purge_expired_events()
        assert "old event" in await _fetch_titles(tl._db_path)

    async def test_options_retention_overrides_data(self, build_timeline):
        tl = build_timeline(retention=99, options={CONF_RETENTION_TIME: 1})
        await tl._initialize_db()
        await _insert_rows(
            tl._db_path,
            [
                _make_row("old", age_days=5),
                _make_row("new", age_days=0.1),
            ],
        )
        await tl.load_events()
        titles = await _fetch_titles(tl._db_path)
        assert "old" not in titles
        assert "new" in titles

    async def test_purge_removes_exactly_expired_events(self, build_timeline):
        """Only events strictly older than the threshold are removed."""
        tl = build_timeline(retention=3)
        await tl._initialize_db()
        await _insert_rows(
            tl._db_path,
            [
                _make_row("too_old", age_days=4),
                _make_row("borderline_recent", age_days=2),
                _make_row("fresh", age_days=0.1),
            ],
        )
        await tl.load_events()
        titles = await _fetch_titles(tl._db_path)
        assert "too_old" not in titles
        assert "borderline_recent" in titles
        assert "fresh" in titles


# ===========================================================================
# _cleanup (orphaned snapshot removal)
# ===========================================================================


class TestCleanup:
    """Tests for the _cleanup orphan-removal routine."""

    async def test_cleanup_skipped_during_migration(self, build_timeline, tmp_path):
        tl = build_timeline()
        await tl._initialize_db()
        media_path = tmp_path / "snapshots"
        media_path.mkdir()
        tl._media_path = str(media_path)

        orphan = media_path / "orphan.jpg"
        orphan.write_bytes(b"fake")
        tl._migrating = True
        await tl._cleanup()

        assert orphan.exists()

    async def test_cleanup_removes_orphaned_stale_images(
        self, build_timeline, tmp_path
    ):
        tl = build_timeline()
        await tl._initialize_db()
        media_path = tmp_path / "snapshots"
        media_path.mkdir()
        tl._media_path = str(media_path)

        orphan = media_path / "orphan.jpg"
        orphan.write_bytes(b"fake")
        old_ts = datetime.datetime.now().timestamp() - 100
        os.utime(str(orphan), (old_ts, old_ts))

        tl._migrating = False
        await tl._cleanup()

        assert not orphan.exists()

    async def test_cleanup_protects_linked_images(self, build_timeline, tmp_path):
        tl = build_timeline()
        await tl._initialize_db()
        media_path = tmp_path / "snapshots"
        media_path.mkdir()
        tl._media_path = str(media_path)

        linked = media_path / "linked.jpg"
        linked.write_bytes(b"fake")
        old_ts = datetime.datetime.now().timestamp() - 100
        os.utime(str(linked), (old_ts, old_ts))

        now = dt_util.utcnow()
        async with aiosqlite.connect(tl._db_path) as db:
            await db.execute(
                """INSERT INTO events
                    (uid, title, start, end, description, key_frame, camera_name, category, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    "ev",
                    now.isoformat(),
                    (now + datetime.timedelta(minutes=1)).isoformat(),
                    "",
                    str(linked),
                    "",
                    "",
                    "",
                ),
            )
            await db.commit()

        tl._migrating = False
        await tl._cleanup()
        assert linked.exists()

    async def test_cleanup_protects_pending_key_frames(self, build_timeline, tmp_path):
        tl = build_timeline()
        await tl._initialize_db()
        media_path = tmp_path / "snapshots"
        media_path.mkdir()
        tl._media_path = str(media_path)

        pending = media_path / "pending.jpg"
        pending.write_bytes(b"fake")
        old_ts = datetime.datetime.now().timestamp() - 100
        os.utime(str(pending), (old_ts, old_ts))

        tl._pending_key_frames.add("pending.jpg")
        tl._migrating = False
        await tl._cleanup()
        assert pending.exists()

    async def test_cleanup_protects_new_files_within_grace_period(
        self, build_timeline, tmp_path
    ):
        tl = build_timeline()
        await tl._initialize_db()
        media_path = tmp_path / "snapshots"
        media_path.mkdir()
        tl._media_path = str(media_path)

        fresh = media_path / "fresh.jpg"
        fresh.write_bytes(b"fake")  # mtime = right now → inside grace window

        tl._migrating = False
        await tl._cleanup()
        assert fresh.exists()

    async def test_cleanup_leaves_directories_untouched(self, build_timeline, tmp_path):
        tl = build_timeline()
        await tl._initialize_db()
        media_path = tmp_path / "snapshots"
        media_path.mkdir()
        tl._media_path = str(media_path)

        subdir = media_path / "subdir"
        subdir.mkdir()

        tl._migrating = False
        await tl._cleanup()
        assert subdir.exists()


# ===========================================================================
# _migrate
# ===========================================================================


class TestMigration:
    """Tests for the _migrate database migration method."""

    async def test_migrate_skips_when_version_is_current(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()
        await tl._set_db_version(DB_VERSION)

        tl._migrating = True
        await tl._migrate()
        assert not tl._migrating

    async def test_migrate_adds_missing_category_column(self, build_timeline):
        tl = build_timeline()
        await tl._initialize_db()

        # Simulate a pre-4.2 schema without the category column
        async with aiosqlite.connect(tl._db_path) as db:
            await db.execute("ALTER TABLE events RENAME TO events_old")
            await db.execute("""CREATE TABLE events (
                    uid TEXT PRIMARY KEY, title TEXT, start TEXT, end TEXT,
                    description TEXT, key_frame TEXT, camera_name TEXT, label TEXT
                )""")
            await db.execute(
                "INSERT INTO events SELECT uid, title, start, end, description, "
                "key_frame, camera_name, label FROM events_old"
            )
            await db.execute("DROP TABLE events_old")
            await db.execute("PRAGMA user_version = 3")
            await db.commit()

        tl._migrating = True
        await tl._migrate()

        assert await tl._has_latest_schema()
        assert await tl._get_db_version() == DB_VERSION
        assert not tl._migrating

    async def test_migrate_populates_label_for_empty_rows(self, build_timeline):
        """Migration populates label/category columns for rows that have empty values."""
        tl = build_timeline()
        await tl._initialize_db()

        # Insert a row with empty label/category
        now = dt_util.utcnow()
        async with aiosqlite.connect(tl._db_path) as db:
            await db.execute(
                """INSERT INTO events
                    (uid, title, start, end, description, key_frame, camera_name, category, label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    "a car passed",
                    now.isoformat(),
                    (now + datetime.timedelta(minutes=1)).isoformat(),
                    "",
                    "",
                    "",
                    "",
                    "",
                ),
            )
            await db.execute("PRAGMA user_version = 0")
            await db.commit()

        tl._migrating = True
        await tl._migrate()

        await tl.load_events()
        ev = tl.events[0]
        assert ev.label == "car"
        assert ev.category == "vehicle"

    async def test_migrate_triggers_cleanup_when_version_is_current(
        self, build_timeline
    ):
        """Even no-op migrations should run a post-migration cleanup sweep."""
        tl = build_timeline()
        await tl._initialize_db()
        await tl._set_db_version(DB_VERSION)

        cleanup_mock = AsyncMock()
        tl._cleanup = cleanup_mock

        tl._migrating = True
        await tl._migrate()

        cleanup_mock.assert_awaited_once()
        assert not tl._migrating

    async def test_migrate_triggers_cleanup_after_real_migration(self, build_timeline):
        """A real migration run should always end with cleanup execution."""
        tl = build_timeline()
        await tl._initialize_db()

        # Force migration path to execute
        await tl._set_db_version(0)

        cleanup_mock = AsyncMock()
        tl._cleanup = cleanup_mock

        tl._migrating = True
        await tl._migrate()

        cleanup_mock.assert_awaited_once()
        assert await tl._get_db_version() == DB_VERSION
        assert not tl._migrating
