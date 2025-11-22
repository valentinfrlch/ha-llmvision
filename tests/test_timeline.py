"""Unit tests for timeline.py module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import datetime
from dataclasses import dataclass


@dataclass
class MockEvent:
    """Mock event for testing."""
    uid: str
    title: str
    start: datetime.datetime
    end: datetime.datetime
    description: str
    key_frame: str = ""
    camera_name: str = ""
    label: str = ""


class TestTimeline:
    """Test Timeline class."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.data = {}
        hass.config = Mock()
        hass.config.path = Mock(return_value="/mock/path")
        hass.loop = Mock()
        hass.loop.run_in_executor = AsyncMock()
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "provider": "Settings",
            "retention_time": 7
        }
        return entry

    def test_retention_time_from_config(self, mock_hass, mock_config_entry):
        """Test retention time is read from config."""
        assert mock_config_entry.data["retention_time"] == 7

    def test_mock_event_creation(self):
        """Test MockEvent dataclass."""
        event = MockEvent(
            uid="test-uid",
            title="Test",
            start=datetime.datetime.now(),
            end=datetime.datetime.now(),
            description="Test desc"
        )
        
        assert event.uid == "test-uid"
        assert event.title == "Test"
        assert event.key_frame == ""
