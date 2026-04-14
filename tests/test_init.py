"""Unit tests for __init__.py module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from custom_components.llmvision import ServiceCallData
from custom_components.llmvision.__init__ import (
    _extract_and_strip_best_frame,
    _match_best_frame,
)
from custom_components.llmvision.const import DOMAIN
import datetime


class TestServiceCallData:
    """Test ServiceCallData class."""

    @pytest.fixture
    def mock_data_call(self):
        """Create a mock data call."""
        data_call = Mock()
        data_call.data = Mock()
        now = datetime.datetime.now()
        data_call.data.get = Mock(side_effect=lambda key, default=None: {
            "provider": "test_provider",
            "model": "test_model",
            "message": "test message",
            "store_in_timeline": False,
            "use_memory": False,
            "image_file": None,
            "image_entity": None,
            "video_file": None,
            "event_id": None,
            "interval": 2,
            "duration": 10,
            "max_frames": 3,
            "target_width": 1920,
            "max_tokens": 1000,
            "include_filename": False,
            "expose_images": False,
            "generate_title": False,
            "sensor_entity": "",
            "response_format": "text",
            "structure": None,
            "title_field": "",
            "title": "Test Title",
            "description": "Test Description",
            "start_time": now,
            "end_time": now + datetime.timedelta(minutes=1),
            "image_path": "",
            "camera_entity": "",
            "label": "",
        }.get(key, default))
        return data_call

    def test_init(self, mock_data_call):
        """Test ServiceCallData initialization."""
        service_call = ServiceCallData(mock_data_call)
        
        assert service_call.provider == "test_provider"
        assert service_call.model == "test_model"
        assert service_call.message == "test message"
        assert service_call.store_in_timeline is False
        assert service_call.use_memory is False

    def test_init_with_image_file(self):
        """Test ServiceCallData with image file."""
        data_call = Mock()
        data_call.data = Mock()
        now = datetime.datetime.now()
        data_call.data.get = Mock(side_effect=lambda key, default=None: {
            "provider": "test_provider",
            "image_file": "image1.jpg\nimage2.jpg",
            "start_time": now,
            "end_time": now + datetime.timedelta(minutes=1),
        }.get(key, default))
        
        service_call = ServiceCallData(data_call)
        
        assert service_call.image_paths == ["image1.jpg", "image2.jpg"]

    def test_init_with_video_file(self):
        """Test ServiceCallData with video file."""
        data_call = Mock()
        data_call.data = Mock()
        now = datetime.datetime.now()
        data_call.data.get = Mock(side_effect=lambda key, default=None: {
            "provider": "test_provider",
            "video_file": "video1.mp4\nvideo2.mp4",
            "start_time": now,
            "end_time": now + datetime.timedelta(minutes=1),
        }.get(key, default))
        
        service_call = ServiceCallData(data_call)
        
        assert service_call.video_paths == ["video1.mp4", "video2.mp4"]

    def test_convert_time_input_datetime(self, mock_data_call):
        """Test _convert_time_input_to_datetime with datetime."""
        service_call = ServiceCallData(mock_data_call)
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        
        result = service_call._convert_time_input_to_datetime(dt)
        
        assert result == dt

    def test_convert_time_input_timestamp(self, mock_data_call):
        """Test _convert_time_input_to_datetime with timestamp."""
        service_call = ServiceCallData(mock_data_call)
        timestamp = 1704110400.0  # 2024-01-01 12:00:00 UTC
        
        result = service_call._convert_time_input_to_datetime(timestamp)
        
        assert isinstance(result, datetime.datetime)

    def test_convert_time_input_iso_string(self, mock_data_call):
        """Test _convert_time_input_to_datetime with ISO string."""
        service_call = ServiceCallData(mock_data_call)
        iso_string = "2024-01-01T12:00:00"
        
        result = service_call._convert_time_input_to_datetime(iso_string)
        
        assert isinstance(result, datetime.datetime)

    def test_convert_time_input_invalid(self, mock_data_call):
        """Test _convert_time_input_to_datetime with invalid input."""
        service_call = ServiceCallData(mock_data_call)
        
        with pytest.raises((ValueError, TypeError)):
            service_call._convert_time_input_to_datetime("invalid")

    def test_get_service_call_data(self, mock_data_call):
        """Test get_service_call_data method."""
        service_call = ServiceCallData(mock_data_call)
        
        result = service_call.get_service_call_data()
        
        assert result == service_call



class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    @pytest.mark.asyncio
    async def test_setup_entry_basic(self):
        """Test basic setup entry."""
        from custom_components.llmvision import async_setup_entry
        
        hass = Mock()
        hass.data = {}
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "provider": "OpenAI",
            "api_key": "test_key",
            "default_model": "gpt-4"
        }
        
        result = await async_setup_entry(hass, entry)
        
        assert result is True
        assert DOMAIN in hass.data
        assert "test_entry" in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_setup_entry_filters_none_values(self):
        """Test setup entry filters None values."""
        from custom_components.llmvision import async_setup_entry
        
        hass = Mock()
        hass.data = {}
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {
            "provider": "OpenAI",
            "api_key": "test_key",
            "default_model": None,
            "temperature": 0.5
        }
        
        result = await async_setup_entry(hass, entry)
        
        assert result is True
        assert "default_model" not in hass.data[DOMAIN]["test_entry"]
        assert "temperature" in hass.data[DOMAIN]["test_entry"]


class TestAsyncRemoveEntry:
    """Test async_remove_entry function."""

    @pytest.mark.asyncio
    async def test_remove_entry(self):
        """Test removing an entry."""
        from custom_components.llmvision import async_remove_entry, async_unload_entry
        
        hass = Mock()
        hass.data = {DOMAIN: {"test_entry": {"provider": "OpenAI"}}}
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"provider": "OpenAI"}
        
        with patch('custom_components.llmvision.async_unload_entry', new=AsyncMock(return_value=True)):
            result = await async_remove_entry(hass, entry)
        
        assert result is True
        assert "test_entry" not in hass.data[DOMAIN]


class TestAsyncUnloadEntry:
    """Test async_unload_entry function."""

    @pytest.mark.asyncio
    async def test_unload_entry_with_calendar(self):
        """Test unloading entry with calendar."""
        from custom_components.llmvision import async_unload_entry
        
        hass = Mock()
        hass.config_entries = Mock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        entry = Mock()
        entry.data = {"retention_time": 7}
        
        result = await async_unload_entry(hass, entry)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_unload_entry_without_calendar(self):
        """Test unloading entry without calendar."""
        from custom_components.llmvision import async_unload_entry

        hass = Mock()
        entry = Mock()
        entry.data = {"provider": "OpenAI"}

        result = await async_unload_entry(hass, entry)

        assert result is True


class TestMatchBestFrame:
    """Test _match_best_frame helper function."""

    def _make_candidates(self):
        return [
            ("camera0-frame-1", "b64data1", "camera0"),
            ("camera0-frame-2", "b64data2", "camera0"),
            ("camera0-frame-3", "b64data3", "camera0"),
        ]

    def test_exact_match(self):
        """Test exact label match."""
        assert _match_best_frame("camera0-frame-2", self._make_candidates()) == 1

    def test_partial_match(self):
        """Test partial matching when exact match fails."""
        # "camera0-frame-2" is contained in "camera0-frame-2:"
        assert _match_best_frame("camera0-frame-2:", self._make_candidates()) == 1

    def test_no_match(self):
        """Test returns None when label doesn't match any candidate."""
        assert _match_best_frame("nonexistent-99", self._make_candidates()) is None

    def test_empty_candidates(self):
        """Test returns None with empty candidates list."""
        assert _match_best_frame("camera0-frame-1", []) is None

    def test_none_label(self):
        """Test returns None with None label."""
        assert _match_best_frame(None, self._make_candidates()) is None

    def test_empty_label(self):
        """Test returns None with empty string label."""
        assert _match_best_frame("", self._make_candidates()) is None


class TestExtractAndStripBestFrame:
    """Test _extract_and_strip_best_frame function."""

    def _make_candidates(self):
        return [
            ("camera0-frame-1", "b64data1", "camera0"),
            ("camera0-frame-2", "b64data2", "camera0"),
            ("camera0-frame-3", "b64data3", "camera0"),
        ]

    def test_extract_from_structured_response(self):
        """Test best_frame extracted and stripped from structured_response."""
        response = {
            "structured_response": {
                "description": "A person at the door",
                "best_frame": "camera0-frame-2",
            }
        }
        candidates = self._make_candidates()

        result = _extract_and_strip_best_frame(response, candidates)

        assert result == 1
        assert "best_frame" not in response["structured_response"]
        assert response["structured_response"]["description"] == "A person at the door"

    def test_extract_from_bracketed_tag(self):
        """Test best_frame extracted from [BEST_FRAME: ...] tag in text."""
        response = {
            "response_text": "A person was seen.\n[BEST_FRAME: camera0-frame-3]"
        }
        candidates = self._make_candidates()

        result = _extract_and_strip_best_frame(response, candidates)

        assert result == 2
        assert "BEST_FRAME" not in response["response_text"]
        assert "A person was seen." in response["response_text"]

    def test_strips_tag_from_text(self):
        """Test that the tag is removed from response_text."""
        response = {
            "response_text": "Delivery at the door. [BEST_FRAME: camera0-frame-1]"
        }
        candidates = self._make_candidates()

        _extract_and_strip_best_frame(response, candidates)

        assert response["response_text"] == "Delivery at the door."

    def test_no_tag_leaves_text_unchanged(self):
        """Test response_text is unchanged when no tag is present."""
        response = {
            "response_text": "A person was detected at the front door."
        }
        candidates = self._make_candidates()

        result = _extract_and_strip_best_frame(response, candidates)

        assert result is None
        assert response["response_text"] == "A person was detected at the front door."

    def test_returns_none_on_invalid_label(self):
        """Test returns None when label doesn't match any candidate."""
        response = {
            "structured_response": {"best_frame": "nonexistent-frame-99"}
        }
        candidates = self._make_candidates()

        result = _extract_and_strip_best_frame(response, candidates)

        assert result is None

    def test_empty_response(self):
        """Test returns None with empty response dict."""
        result = _extract_and_strip_best_frame({}, self._make_candidates())
        assert result is None

    def test_structured_takes_priority_over_text(self):
        """Test structured_response best_frame is used over text tag."""
        response = {
            "structured_response": {
                "best_frame": "camera0-frame-1",
            },
            "response_text": "text [BEST_FRAME: camera0-frame-3]",
        }
        candidates = self._make_candidates()

        result = _extract_and_strip_best_frame(response, candidates)

        # Structured wins
        assert result == 0
        # But text tag should still be stripped
        assert "BEST_FRAME" not in response["response_text"]
