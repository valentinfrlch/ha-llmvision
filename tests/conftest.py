"""Pytest configuration and fixtures for llmvision tests."""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock
from homeassistant.config_entries import ConfigEntry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.data = {}
    hass.config_entries = Mock()
    hass.config_entries.async_entries = Mock(return_value=[])
    hass.loop = Mock()
    hass.loop.run_in_executor = AsyncMock()
    hass.config = Mock()
    hass.config.path = Mock(return_value="/mock/path")
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {
        "provider": "Settings",
        "system_prompt": "Test system prompt",
        "title_prompt": "Test title prompt",
        "memory_strings": [],
        "memory_paths": [],
        "memory_images_encoded": [],
    }
    return entry
