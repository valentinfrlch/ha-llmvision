"""Unit tests for __init__.py module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from custom_components.llmvision import ServiceCallData
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
