"""Unit tests for memory.py module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from custom_components.llmvision.memory import Memory
from custom_components.llmvision.const import (
    DOMAIN,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TITLE_PROMPT,
)


class TestMemory:
    """Test Memory class."""

    def test_init_without_entry(self, mock_hass):
        """Test Memory initialization without config entry."""
        memory = Memory(mock_hass, strings=["test"], paths=[])
        
        assert memory.hass == mock_hass
        assert memory.memory_strings == ["test"]
        assert memory.memory_paths == []
        assert memory.memory_images == []
        assert memory._system_prompt == DEFAULT_SYSTEM_PROMPT
        assert memory._title_prompt == DEFAULT_TITLE_PROMPT

    def test_init_with_custom_prompt(self, mock_hass):
        """Test Memory initialization with custom system prompt."""
        custom_prompt = "Custom prompt"
        memory = Memory(mock_hass, system_prompt=custom_prompt)
        
        assert memory._system_prompt == custom_prompt

    def test_init_with_entry(self, mock_hass, mock_config_entry):
        """Test Memory initialization with config entry."""
        mock_hass.config_entries.async_entries = Mock(return_value=[mock_config_entry])
        
        memory = Memory(mock_hass)
        
        assert memory.entry == mock_config_entry
        assert memory._system_prompt == "Test system prompt"
        assert memory._title_prompt == "Test title prompt"

    def test_system_prompt_property(self, mock_hass):
        """Test system_prompt property."""
        memory = Memory(mock_hass)
        assert memory.system_prompt.startswith("System prompt: ")

    def test_title_prompt_property(self, mock_hass):
        """Test title_prompt property."""
        memory = Memory(mock_hass)
        assert memory.title_prompt == DEFAULT_TITLE_PROMPT

    def test_get_memory_images_openai_empty(self, mock_hass):
        """Test _get_memory_images with OpenAI format and no images."""
        memory = Memory(mock_hass)
        result = memory._get_memory_images(memory_type="OpenAI")
        
        assert result == []

    def test_get_memory_images_openai_with_images(self, mock_hass):
        """Test _get_memory_images with OpenAI format and images."""
        memory = Memory(mock_hass, strings=["Image 1"], paths=[])
        memory.memory_images = ["base64_encoded_image"]
        
        result = memory._get_memory_images(memory_type="OpenAI")
        
        assert len(result) == 3  # prompt + text + image
        assert result[0]["type"] == "text"
        assert "reference" in result[0]["text"]
        assert result[1]["type"] == "text"
        assert result[1]["text"] == "Image 1:"
        assert result[2]["type"] == "image_url"

    def test_get_memory_images_anthropic(self, mock_hass):
        """Test _get_memory_images with Anthropic format."""
        memory = Memory(mock_hass, strings=["Test"], paths=[])
        memory.memory_images = ["base64_image"]
        
        result = memory._get_memory_images(memory_type="Anthropic")
        
        assert len(result) == 3
        assert result[2]["type"] == "image"
        assert result[2]["source"]["type"] == "base64"

    def test_get_memory_images_google(self, mock_hass):
        """Test _get_memory_images with Google format."""
        memory = Memory(mock_hass, strings=["Test"], paths=[])
        memory.memory_images = ["base64_image"]
        
        result = memory._get_memory_images(memory_type="Google")
        
        assert len(result) == 3
        assert "inline_data" in result[2]

    def test_get_memory_images_ollama(self, mock_hass):
        """Test _get_memory_images with Ollama format."""
        memory = Memory(mock_hass, strings=["Test"], paths=[])
        memory.memory_images = ["base64_image"]
        
        result = memory._get_memory_images(memory_type="Ollama")
        
        assert len(result) == 2
        assert result[1]["role"] == "user"
        assert "images" in result[1]

    def test_get_memory_images_aws(self, mock_hass):
        """Test _get_memory_images with AWS format."""
        import base64
        memory = Memory(mock_hass, strings=["Test"], paths=[])
        # Use valid base64 encoded data
        memory.memory_images = [base64.b64encode(b"test_image_data").decode("utf-8")]
        
        result = memory._get_memory_images(memory_type="AWS")
        
        assert len(result) == 3
        assert "image" in result[2]

    def test_get_memory_images_unknown_type(self, mock_hass):
        """Test _get_memory_images with unknown memory type."""
        memory = Memory(mock_hass)
        result = memory._get_memory_images(memory_type="Unknown")
        
        assert result is None

    def test_str_representation(self, mock_hass):
        """Test __str__ method."""
        memory = Memory(mock_hass, strings=["test"], paths=["path"])
        memory.memory_images = ["img1", "img2"]
        
        result = str(memory)
        
        assert "Memory" in result
        assert "['test']" in result
        assert "['path']" in result
        assert "2" in result

    def test_find_memory_entry_not_found(self, mock_hass):
        """Test _find_memory_entry when no Settings entry exists."""
        memory = Memory(mock_hass)
        assert memory.entry is None

    def test_find_memory_entry_found(self, mock_hass, mock_config_entry):
        """Test _find_memory_entry when Settings entry exists."""
        mock_hass.config_entries.async_entries = Mock(return_value=[mock_config_entry])
        
        memory = Memory(mock_hass)
        
        assert memory.entry == mock_config_entry



class TestMemoryAdvanced:
    """Advanced tests for Memory class."""

    def test_get_memory_images_openai_legacy(self, mock_hass):
        """Test _get_memory_images with OpenAI-legacy format."""
        memory = Memory(mock_hass, strings=["Test"], paths=[])
        memory.memory_images = ["base64_image"]
        
        result = memory._get_memory_images(memory_type="OpenAI-legacy")
        
        assert len(result) == 3
        assert result[0]["type"] == "text"
        assert result[2]["type"] == "image_url"

    def test_get_memory_images_multiple_images(self, mock_hass):
        """Test _get_memory_images with multiple images."""
        memory = Memory(mock_hass, strings=["Image 1", "Image 2"], paths=[])
        memory.memory_images = ["base64_1", "base64_2"]
        
        result = memory._get_memory_images(memory_type="OpenAI")
        
        # Should have: prompt + (text + image) * 2 = 5 items
        assert len(result) == 5

    def test_memory_with_empty_strings(self, mock_hass):
        """Test Memory with empty strings list."""
        memory = Memory(mock_hass, strings=[], paths=[])
        
        assert memory.memory_strings == []
        assert memory.memory_paths == []

    def test_memory_with_paths_no_images(self, mock_hass):
        """Test Memory with paths but no encoded images."""
        memory = Memory(mock_hass, strings=["test"], paths=["/path/to/image.jpg"])
        
        assert len(memory.memory_paths) == 1
        assert len(memory.memory_images) == 0

    def test_system_prompt_includes_prefix(self, mock_hass):
        """Test system_prompt property includes prefix."""
        memory = Memory(mock_hass)
        
        result = memory.system_prompt
        
        assert result.startswith("System prompt: ")

    def test_title_prompt_no_prefix(self, mock_hass):
        """Test title_prompt property has no prefix."""
        memory = Memory(mock_hass)
        
        result = memory.title_prompt
        
        assert not result.startswith("System prompt:")
        assert isinstance(result, str)

    def test_find_memory_entry_multiple_entries(self, mock_hass, mock_config_entry):
        """Test _find_memory_entry with multiple entries."""
        other_entry = Mock()
        other_entry.data = {"provider": "OpenAI"}
        
        mock_hass.config_entries.async_entries = Mock(
            return_value=[other_entry, mock_config_entry]
        )
        
        memory = Memory(mock_hass)
        
        assert memory.entry == mock_config_entry

    def test_memory_initialization_with_all_params(self, mock_hass):
        """Test Memory initialization with all parameters."""
        memory = Memory(
            mock_hass,
            strings=["test1", "test2"],
            paths=["/path1", "/path2"],
            system_prompt="Custom prompt"
        )
        
        assert len(memory.memory_strings) == 2
        assert len(memory.memory_paths) == 2
        assert memory._system_prompt == "Custom prompt"
