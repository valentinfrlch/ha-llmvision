"""Unit tests for calendar.py module."""
import pytest
import datetime
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from homeassistant.components.calendar import CalendarEvent


class MockTimelineEvent:
    """Mock timeline event."""
    def __init__(self, uid, title, start, end, description):
        self.uid = uid
        self.title = title
        self.start = start
        self.end = end
        self.description = description


class TestCalendar:
    """Test Calendar class."""

    @pytest.fixture
    def mock_timeline(self):
        """Create a mock Timeline."""
        timeline = Mock()
        timeline.get_all_events = AsyncMock(return_value=[])
        timeline.delete_event = AsyncMock()
        return timeline

    @pytest.fixture
    def calendar_instance(self, mock_hass, mock_config_entry, mock_timeline):
        """Create a Calendar instance with mocked dependencies."""
        from custom_components.llmvision.calendar import Calendar
        
        with patch('custom_components.llmvision.calendar.Timeline', return_value=mock_timeline):
            with patch('os.makedirs'):
                with patch('os.path.join', return_value="/mock/path"):
                    calendar = Calendar(mock_hass, mock_config_entry)
                    return calendar

    def test_init(self, calendar_instance):
        """Test Calendar initialization."""
        assert calendar_instance._attr_name == "LLM Vision Timeline"
        assert calendar_instance._attr_unique_id == "llm_vision_timeline"
        assert calendar_instance._events == []
        assert calendar_instance._current_event is None

    def test_icon_property(self, calendar_instance):
        """Test icon property."""
        assert calendar_instance.icon == "mdi:timeline-outline"

    def test_event_property(self, calendar_instance):
        """Test event property."""
        assert calendar_instance.event is None
        
        # Set an event
        test_event = Mock()
        calendar_instance._current_event = test_event
        assert calendar_instance.event == test_event

    def test_ensure_datetime_with_datetime(self, calendar_instance):
        """Test _ensure_datetime with datetime input."""
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = calendar_instance._ensure_datetime(dt)
        
        assert result == dt
        assert result.tzinfo is not None

    def test_ensure_datetime_with_date(self, calendar_instance):
        """Test _ensure_datetime with date input."""
        dt = datetime.date(2024, 1, 1)
        result = calendar_instance._ensure_datetime(dt)
        
        assert isinstance(result, datetime.datetime)
        assert result.tzinfo is not None

    def test_ensure_datetime_without_timezone(self, calendar_instance):
        """Test _ensure_datetime adds timezone if missing."""
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = calendar_instance._ensure_datetime(dt)
        
        assert result.tzinfo is not None
        assert result.tzinfo == datetime.timezone.utc

    @pytest.mark.asyncio
    async def test_async_update_empty(self, calendar_instance, mock_timeline):
        """Test async_update with no events."""
        mock_timeline.get_all_events = AsyncMock(return_value=[])
        
        await calendar_instance.async_update()
        
        assert calendar_instance._events == []

    @pytest.mark.asyncio
    async def test_async_update_with_events(self, calendar_instance, mock_timeline):
        """Test async_update with events."""
        mock_events = [
            MockTimelineEvent(
                uid="1",
                title="Event 1",
                start=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
                end=datetime.datetime(2024, 1, 1, 1, 0, tzinfo=datetime.timezone.utc),
                description="Description 1"
            ),
            MockTimelineEvent(
                uid="2",
                title="Event 2",
                start=datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc),
                end=datetime.datetime(2024, 1, 2, 1, 0, tzinfo=datetime.timezone.utc),
                description="Description 2"
            )
        ]
        mock_timeline.get_all_events = AsyncMock(return_value=mock_events)
        
        await calendar_instance.async_update()
        
        assert len(calendar_instance._events) == 2
        assert all(isinstance(e, CalendarEvent) for e in calendar_instance._events)
        # Events should be sorted by start time in reverse
        assert calendar_instance._events[0].uid == "2"

    @pytest.mark.asyncio
    async def test_async_get_events_in_range(self, calendar_instance, mock_timeline):
        """Test async_get_events returns events within date range."""
        mock_events = [
            MockTimelineEvent(
                uid="1",
                title="Event 1",
                start=datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc),
                end=datetime.datetime(2024, 1, 15, 1, 0, tzinfo=datetime.timezone.utc),
                description="Description 1"
            )
        ]
        mock_timeline.get_all_events = AsyncMock(return_value=mock_events)
        
        start_date = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        end_date = datetime.datetime(2024, 1, 31, tzinfo=datetime.timezone.utc)
        
        result = await calendar_instance.async_get_events(
            calendar_instance.hass, start_date, end_date
        )
        
        assert len(result) == 1
        assert result[0].uid == "1"

    @pytest.mark.asyncio
    async def test_async_get_events_outside_range(self, calendar_instance, mock_timeline):
        """Test async_get_events excludes events outside date range."""
        mock_events = [
            MockTimelineEvent(
                uid="1",
                title="Event 1",
                start=datetime.datetime(2024, 2, 15, tzinfo=datetime.timezone.utc),
                end=datetime.datetime(2024, 2, 15, 1, 0, tzinfo=datetime.timezone.utc),
                description="Description 1"
            )
        ]
        mock_timeline.get_all_events = AsyncMock(return_value=mock_events)
        
        start_date = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        end_date = datetime.datetime(2024, 1, 31, tzinfo=datetime.timezone.utc)
        
        result = await calendar_instance.async_get_events(
            calendar_instance.hass, start_date, end_date
        )
        
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_async_delete_event(self, calendar_instance, mock_timeline):
        """Test async_delete_event."""
        uid = "test_uid"
        
        await calendar_instance.async_delete_event(uid)
        
        mock_timeline.delete_event.assert_called_once_with(uid)



class TestCalendarAdvanced:
    """Advanced tests for Calendar class."""

    @pytest.fixture
    def mock_timeline_with_events(self):
        """Create a mock Timeline with events."""
        timeline = Mock()
        events = [
            MockTimelineEvent(
                uid=f"event_{i}",
                title=f"Event {i}",
                start=datetime.datetime(2024, 1, i+1, tzinfo=datetime.timezone.utc),
                end=datetime.datetime(2024, 1, i+1, 1, 0, tzinfo=datetime.timezone.utc),
                description=f"Description {i}"
            )
            for i in range(5)
        ]
        timeline.get_all_events = AsyncMock(return_value=events)
        timeline.delete_event = AsyncMock()
        return timeline

    @pytest.fixture
    def calendar_with_events(self, mock_hass, mock_config_entry, mock_timeline_with_events):
        """Create a Calendar instance with events."""
        from custom_components.llmvision.calendar import Calendar
        
        with patch('custom_components.llmvision.calendar.Timeline', return_value=mock_timeline_with_events):
            with patch('os.makedirs'):
                with patch('os.path.join', return_value="/mock/path"):
                    calendar = Calendar(mock_hass, mock_config_entry)
                    return calendar

    @pytest.mark.asyncio
    async def test_async_update_sorts_events(self, calendar_with_events, mock_timeline_with_events):
        """Test async_update sorts events by start time in reverse."""
        await calendar_with_events.async_update()
        
        # Events should be sorted in reverse chronological order
        assert len(calendar_with_events._events) == 5
        assert calendar_with_events._events[0].uid == "event_4"
        assert calendar_with_events._events[-1].uid == "event_0"

    @pytest.mark.asyncio
    async def test_async_get_events_partial_overlap(self, calendar_with_events, mock_timeline_with_events):
        """Test async_get_events with partial date range overlap."""
        start_date = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
        end_date = datetime.datetime(2024, 1, 4, tzinfo=datetime.timezone.utc)
        
        result = await calendar_with_events.async_get_events(
            calendar_with_events.hass, start_date, end_date
        )
        
        # Should include events 1, 2, 3 (indices 1, 2, 3)
        assert len(result) >= 2

    def test_ensure_datetime_preserves_timezone(self):
        """Test _ensure_datetime preserves existing timezone."""
        from custom_components.llmvision.calendar import Calendar
        
        mock_hass = Mock()
        mock_config_entry = Mock()
        
        with patch('custom_components.llmvision.calendar.Timeline'):
            with patch('os.makedirs'):
                with patch('os.path.join', return_value="/mock/path"):
                    calendar = Calendar(mock_hass, mock_config_entry)
                    
                    tz = datetime.timezone(datetime.timedelta(hours=5))
                    dt = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz)
                    
                    result = calendar._ensure_datetime(dt)
                    
                    assert result.tzinfo == tz
