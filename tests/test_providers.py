"""Unit tests for providers.py module."""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from homeassistant.exceptions import ServiceValidationError
from custom_components.llmvision.providers import (
    Request,
    Provider,
    OpenAI,
    Anthropic,
    Google,
)
from custom_components.llmvision.const import DOMAIN


@pytest.fixture
def mock_hass_with_session():
    """Create a mock Home Assistant instance with session."""
    hass = Mock()
    hass.data = {}
    hass.config_entries = Mock()
    hass.config_entries.async_entries = Mock(return_value=[])
    hass.loop = Mock()
    hass.loop.run_in_executor = AsyncMock()
    hass.config = Mock()
    hass.config.path = Mock(return_value="/mock/path")
    return hass


class TestRequest:
    """Test Request class."""

    def test_init(self, mock_hass_with_session):
        """Test Request initialization."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            request = Request(mock_hass_with_session, "test message", 1000, 0.5)
        
            assert request.hass == mock_hass_with_session
            assert request.message == "test message"
            assert request.max_tokens == 1000
            assert request.temperature == 0.5
            assert request.base64_images == []
            assert request.filenames == []

    def test_sanitize_data_dict(self):
        """Test sanitize_data with dictionary."""
        data = {"key": "value", "long_string": "a" * 500}
        result = Request.sanitize_data(data)
        
        assert result["key"] == "value"
        assert result["long_string"] == "<long_string>"

    def test_sanitize_data_list(self):
        """Test sanitize_data with list."""
        data = ["short", "a" * 500]
        result = Request.sanitize_data(data)
        
        assert result[0] == "short"
        assert result[1] == "<long_string>"

    def test_sanitize_data_bytes(self):
        """Test sanitize_data with bytes."""
        data = {"bytes": b"a" * 500}
        result = Request.sanitize_data(data)
        
        assert result["bytes"] == "<long_bytes>"

    def test_get_provider(self, mock_hass):
        """Test get_provider method."""
        mock_hass.data = {
            DOMAIN: {
                "test_uid": {"provider": "OpenAI"}
            }
        }
        
        result = Request.get_provider(mock_hass, "test_uid")
        
        assert result == "OpenAI"

    def test_get_provider_not_found(self, mock_hass):
        """Test get_provider when provider not found."""
        mock_hass.data = {}
        
        result = Request.get_provider(mock_hass, "nonexistent")
        
        assert result is None

    def test_get_default_model_from_config(self, mock_hass_with_session):
        """Test get_default_model from config entry."""
        mock_hass_with_session.data = {
            DOMAIN: {
                "test_provider": {
                    "provider": "OpenAI",
                    "default_model": "gpt-4"
                }
            }
        }
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            request = Request(mock_hass_with_session, "test", 1000, 0.5)
            
            result = request.get_default_model("test_provider")
            
            assert result == "gpt-4"

    def test_get_default_model_fallback(self, mock_hass_with_session):
        """Test get_default_model fallback to defaults."""
        mock_hass_with_session.data = {
            DOMAIN: {
                "test_provider": {
                    "provider": "OpenAI"
                }
            }
        }
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            request = Request(mock_hass_with_session, "test", 1000, 0.5)
            
            result = request.get_default_model("test_provider")
            
            assert result == "gpt-4o-mini"

    def test_add_frame(self, mock_hass_with_session):
        """Test add_frame method."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            request = Request(mock_hass_with_session, "test", 1000, 0.5)
            
            request.add_frame("base64_image_data", "test_filename")
            
            assert len(request.base64_images) == 1
            assert request.base64_images[0] == "base64_image_data"
            assert request.filenames[0] == "test_filename"

    def test_validate_no_images(self, mock_hass_with_session):
        """Test validate raises error when no images provided."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            request = Request(mock_hass_with_session, "test", 1000, 0.5)
            call = Mock()
            call.model = "gpt-4"
            call.base64_images = []
            call.provider = "test_provider"
            
            with pytest.raises(ServiceValidationError):
                request.validate(call)

    def test_validate_groq_multiple_images(self, mock_hass_with_session):
        """Test validate raises error for Groq with multiple images."""
        mock_hass_with_session.data = {
            DOMAIN: {
                "test_provider": {"provider": "Groq"}
            }
        }
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            request = Request(mock_hass_with_session, "test", 1000, 0.5)
            call = Mock()
            call.model = "test-model"
            call.base64_images = ["img1", "img2"]
            call.provider = "test_provider"
            
            with pytest.raises(ServiceValidationError):
                request.validate(call)

    def test_validate_success(self, mock_hass_with_session):
        """Test validate succeeds with valid data."""
        mock_hass_with_session.data = {
            DOMAIN: {
                "test_provider": {"provider": "OpenAI"}
            }
        }
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            request = Request(mock_hass_with_session, "test", 1000, 0.5)
            call = Mock()
            call.model = "gpt-4"
            call.base64_images = ["img1"]
            call.provider = "test_provider"
            
            # Should not raise
            request.validate(call)


class TestOpenAI:
    """Test OpenAI provider class."""

    def test_init(self, mock_hass_with_session):
        """Test OpenAI initialization."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            openai = OpenAI(mock_hass_with_session, "test_api_key", "gpt-4")
            
            assert openai.api_key == "test_api_key"
            assert openai.model == "gpt-4"
            assert openai.hass == mock_hass_with_session

    def test_supports_structured_output(self, mock_hass_with_session):
        """Test supports_structured_output returns True."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            openai = OpenAI(mock_hass_with_session, "test_api_key", "gpt-4")
            
            assert openai.supports_structured_output() is True

    def test_generate_headers(self, mock_hass_with_session):
        """Test _generate_headers method."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            openai = OpenAI(mock_hass_with_session, "test_api_key", "gpt-4")
            
            headers = openai._generate_headers()
            
            assert headers["Content-type"] == "application/json"
            assert headers["Authorization"] == "Bearer test_api_key"

    def test_prepare_vision_data_basic(self, mock_hass_with_session):
        """Test _prepare_vision_data with basic call."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            openai = OpenAI(mock_hass_with_session, "test_api_key", "gpt-4")
            call = Mock()
            call.max_tokens = 1000
            call.base64_images = ["base64_image"]
            call.filenames = ["test.jpg"]
            call.message = "Describe this image"
            call.provider = "test_provider"
            call.response_format = "text"
            call.use_memory = False
            
            mock_hass_with_session.data = {
                DOMAIN: {
                    "test_provider": {
                        "provider": "OpenAI",
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                }
            }
            
            with patch.object(openai, '_get_system_prompt', return_value="System prompt"):
                result = openai._prepare_vision_data(call)
            
            assert result["model"] == "gpt-4"
            assert result["max_completion_tokens"] == 1000
            assert len(result["messages"]) == 2  # system + user
            assert result["messages"][0]["role"] == "system"
            assert result["messages"][1]["role"] == "user"

    def test_prepare_text_data(self, mock_hass_with_session):
        """Test _prepare_text_data method."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            openai = OpenAI(mock_hass_with_session, "test_api_key", "gpt-4")
            call = Mock()
            call.max_tokens = 1000
            call.message = "Generate a title"
            call.provider = "test_provider"
            
            mock_hass_with_session.data = {
                DOMAIN: {
                    "test_provider": {
                        "provider": "OpenAI",
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                }
            }
            
            with patch.object(openai, '_get_title_prompt', return_value="Title prompt"):
                result = openai._prepare_text_data(call)
            
            assert result["model"] == "gpt-4"
            assert result["max_completion_tokens"] == 1000
            assert len(result["messages"]) == 2


class TestAnthropic:
    """Test Anthropic provider class."""

    def test_init(self, mock_hass_with_session):
        """Test Anthropic initialization."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            anthropic = Anthropic(mock_hass_with_session, "test_api_key", "claude-3")
            
            assert anthropic.api_key == "test_api_key"
            assert anthropic.model == "claude-3"

    def test_supports_structured_output(self, mock_hass_with_session):
        """Test supports_structured_output returns True."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            anthropic = Anthropic(mock_hass_with_session, "test_api_key", "claude-3")
            
            assert anthropic.supports_structured_output() is True

    def test_generate_headers(self, mock_hass_with_session):
        """Test _generate_headers method."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            anthropic = Anthropic(mock_hass_with_session, "test_api_key", "claude-3")
            
            headers = anthropic._generate_headers()
            
            assert headers["content-type"] == "application/json"
            assert headers["x-api-key"] == "test_api_key"
            assert "anthropic-version" in headers


class TestGoogle:
    """Test Google provider class."""

    def test_init(self, mock_hass_with_session):
        """Test Google initialization."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            google = Google(mock_hass_with_session, "test_api_key", "gemini-pro")
            
            assert google.api_key == "test_api_key"
            assert google.model == "gemini-pro"

    def test_generate_headers(self, mock_hass_with_session):
        """Test _generate_headers method."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            google = Google(mock_hass_with_session, "test_api_key", "gemini-pro")
            
            headers = google._generate_headers()
            
            assert headers["content-type"] == "application/json"



class TestProviderBase:
    """Test Provider base class methods."""

    def test_get_default_parameters(self, mock_hass_with_session):
        """Test _get_default_parameters method."""
        mock_hass_with_session.data = {
            DOMAIN: {
                "test_provider": {
                    "temperature": 0.8,
                    "top_p": 0.95,
                    "keep_alive": 10,
                    "context_window": 4096
                }
            }
        }
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = OpenAI(mock_hass_with_session, "test_key", "gpt-4")
            call = Mock()
            call.provider = "test_provider"
            
            result = provider._get_default_parameters(call)
            
            assert result["temperature"] == 0.8
            assert result["top_p"] == 0.95

    def test_get_system_prompt_default(self, mock_hass_with_session):
        """Test _get_system_prompt returns default."""
        mock_hass_with_session.data = {DOMAIN: {}}
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = OpenAI(mock_hass_with_session, "test_key", "gpt-4")
            
            result = provider._get_system_prompt()
            
            assert isinstance(result, str)
            assert len(result) > 0

    def test_get_system_prompt_from_settings(self, mock_hass_with_session):
        """Test _get_system_prompt from Settings entry."""
        mock_hass_with_session.data = {
            DOMAIN: {
                "settings_entry": {
                    "provider": "Settings",
                    "system_prompt": "Custom system prompt"
                }
            }
        }
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = OpenAI(mock_hass_with_session, "test_key", "gpt-4")
            
            result = provider._get_system_prompt()
            
            assert result == "Custom system prompt"

    def test_get_title_prompt_default(self, mock_hass_with_session):
        """Test _get_title_prompt returns default."""
        mock_hass_with_session.data = {DOMAIN: {}}
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = OpenAI(mock_hass_with_session, "test_key", "gpt-4")
            
            result = provider._get_title_prompt()
            
            assert isinstance(result, str)
            assert len(result) > 0

    def test_supports_structured_output_default(self, mock_hass_with_session):
        """Test supports_structured_output default implementation."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            # Create a basic provider that doesn't override the method
            from custom_components.llmvision.providers import Provider
            
            # We can't instantiate abstract class, so test through OpenAI
            provider = OpenAI(mock_hass_with_session, "test_key", "gpt-4")
            
            # OpenAI overrides this, so it should return True
            assert provider.supports_structured_output() is True


class TestAzureOpenAI:
    """Test AzureOpenAI provider class."""

    def test_init(self, mock_hass_with_session):
        """Test AzureOpenAI initialization."""
        from custom_components.llmvision.providers import AzureOpenAI
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            azure = AzureOpenAI(
                mock_hass_with_session,
                "test_api_key",
                "gpt-4",
                endpoint={
                    "base_url": "https://test.openai.azure.com/",
                    "endpoint": "https://test.openai.azure.com/",
                    "deployment": "test-deployment",
                    "api_version": "2024-02-01"
                }
            )
            
            assert azure.api_key == "test_api_key"
            assert azure.model == "gpt-4"

    def test_supports_structured_output(self, mock_hass_with_session):
        """Test AzureOpenAI supports structured output."""
        from custom_components.llmvision.providers import AzureOpenAI
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            azure = AzureOpenAI(
                mock_hass_with_session,
                "test_api_key",
                "gpt-4"
            )
            
            assert azure.supports_structured_output() is True

    def test_generate_headers(self, mock_hass_with_session):
        """Test AzureOpenAI _generate_headers method."""
        from custom_components.llmvision.providers import AzureOpenAI
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            azure = AzureOpenAI(
                mock_hass_with_session,
                "test_api_key",
                "gpt-4"
            )
            
            headers = azure._generate_headers()
            
            assert headers["Content-type"] == "application/json"
            assert headers["api-key"] == "test_api_key"


class TestGroq:
    """Test Groq provider class."""

    def test_init(self, mock_hass_with_session):
        """Test Groq initialization."""
        from custom_components.llmvision.providers import Groq
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            groq = Groq(mock_hass_with_session, "test_api_key", "llama-3")
            
            assert groq.api_key == "test_api_key"
            assert groq.model == "llama-3"

    def test_supports_structured_output(self, mock_hass_with_session):
        """Test Groq supports structured output."""
        from custom_components.llmvision.providers import Groq
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            groq = Groq(mock_hass_with_session, "test_api_key", "llama-3")
            
            assert groq.supports_structured_output() is True



class TestLocalAI:
    """Test LocalAI provider class."""

    def test_init(self, mock_hass_with_session):
        """Test LocalAI initialization."""
        from custom_components.llmvision.providers import LocalAI
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            localai = LocalAI(
                mock_hass_with_session,
                "test_api_key",
                "llava",
                endpoint={
                    "ip_address": "localhost",
                    "port": 8080,
                    "https": False
                }
            )
            
            assert localai.api_key == "test_api_key"
            assert localai.model == "llava"


class TestOllama:
    """Test Ollama provider class."""

    def test_init(self, mock_hass_with_session):
        """Test Ollama initialization."""
        from custom_components.llmvision.providers import Ollama
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            ollama = Ollama(
                mock_hass_with_session,
                "",
                "llama2",
                endpoint={
                    "ip_address": "localhost",
                    "port": 11434,
                    "https": False,
                    "keep_alive": "5m",
                    "context_window": 2048
                }
            )
            
            assert ollama.model == "llama2"


class TestProviderFactory:
    """Test ProviderFactory class."""

    def test_create_openai(self, mock_hass_with_session):
        """Test ProviderFactory creates OpenAI provider."""
        from custom_components.llmvision.providers import ProviderFactory
        
        config = {"api_key": "test_key"}
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "OpenAI",
                config,
                "gpt-4"
            )
            
            assert provider is not None
            assert provider.model == "gpt-4"

    def test_create_anthropic(self, mock_hass_with_session):
        """Test ProviderFactory creates Anthropic provider."""
        from custom_components.llmvision.providers import ProviderFactory
        
        config = {"api_key": "test_key"}
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "Anthropic",
                config,
                "claude-3"
            )
            
            assert provider is not None
            assert provider.model == "claude-3"

    def test_create_google(self, mock_hass_with_session):
        """Test ProviderFactory creates Google provider."""
        from custom_components.llmvision.providers import ProviderFactory
        
        config = {"api_key": "test_key"}
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "Google",
                config,
                "gemini-pro"
            )
            
            assert provider is not None
            assert provider.model == "gemini-pro"

    def test_create_groq(self, mock_hass_with_session):
        """Test ProviderFactory creates Groq provider."""
        from custom_components.llmvision.providers import ProviderFactory
        
        config = {"api_key": "test_key"}
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "Groq",
                config,
                "llama-3"
            )
            
            assert provider is not None
            assert provider.model == "llama-3"

    def test_create_azure(self, mock_hass_with_session):
        """Test ProviderFactory creates Azure provider."""
        from custom_components.llmvision.providers import ProviderFactory
        
        config = {
            "api_key": "test_key",
            "azure_base_url": "https://test.openai.azure.com/",
            "azure_deployment": "test-deployment",
            "azure_version": "2024-02-01"
        }
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "Azure",
                config,
                "gpt-4"
            )
            
            assert provider is not None
            assert provider.model == "gpt-4"

    def test_create_localai(self, mock_hass_with_session):
        """Test ProviderFactory creates LocalAI provider."""
        from custom_components.llmvision.providers import ProviderFactory
        
        config = {
            "ip_address": "localhost",
            "port": 8080,
            "https": False
        }
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "LocalAI",
                config,
                "llava"
            )
            
            assert provider is not None
            assert provider.model == "llava"

    def test_create_ollama(self, mock_hass_with_session):
        """Test ProviderFactory creates Ollama provider."""
        from custom_components.llmvision.providers import ProviderFactory
        
        config = {
            "ip_address": "localhost",
            "port": 11434,
            "https": False,
            "keep_alive": "5m",
            "context_window": 2048
        }
        
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "Ollama",
                config,
                "llama2"
            )
            
            assert provider is not None
            assert provider.model == "llama2"

    def test_create_minimax(self, mock_hass_with_session):
        """Test ProviderFactory creates MiniMax provider."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )

            assert provider is not None
            assert provider.model == "MiniMax-M1"
            assert isinstance(provider, OpenAI)

    def test_create_minimax_endpoint(self, mock_hass_with_session):
        """Test ProviderFactory creates MiniMax provider with correct endpoint."""
        from custom_components.llmvision.providers import ProviderFactory
        from custom_components.llmvision.const import ENDPOINT_MINIMAX

        config = {"api_key": "test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )

            assert provider.endpoint.get("base_url") == ENDPOINT_MINIMAX

    def test_create_invalid_provider(self, mock_hass_with_session):
        """Test ProviderFactory raises error for invalid provider."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            with pytest.raises(ServiceValidationError):
                ProviderFactory.create(
                    mock_hass_with_session,
                    "InvalidProvider",
                    config,
                    "model"
                )


class TestMiniMax:
    """Test MiniMax provider (reuses OpenAI class via ProviderFactory)."""

    def test_minimax_is_openai_instance(self, mock_hass_with_session):
        """Test MiniMax provider is an instance of OpenAI."""
        from custom_components.llmvision.providers import ProviderFactory
        from custom_components.llmvision.const import ENDPOINT_MINIMAX

        config = {"api_key": "minimax_test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )

            assert isinstance(provider, OpenAI)
            assert provider.api_key == "minimax_test_key"
            assert provider.model == "MiniMax-M1"
            assert provider.endpoint.get("base_url") == ENDPOINT_MINIMAX

    def test_minimax_supports_structured_output(self, mock_hass_with_session):
        """Test MiniMax provider supports structured output (inherits from OpenAI)."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )

            assert provider.supports_structured_output() is True

    def test_minimax_generate_headers(self, mock_hass_with_session):
        """Test MiniMax provider generates correct headers."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "minimax_api_key_123"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )

            headers = provider._generate_headers()

            assert headers["Content-type"] == "application/json"
            assert headers["Authorization"] == "Bearer minimax_api_key_123"

    def test_minimax_prepare_vision_data(self, mock_hass_with_session):
        """Test MiniMax provider prepares vision data correctly."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )
            call = Mock()
            call.max_tokens = 1000
            call.base64_images = ["base64_image_data"]
            call.filenames = ["test.jpg"]
            call.message = "Describe this image"
            call.provider = "test_provider"
            call.response_format = "text"
            call.use_memory = False

            mock_hass_with_session.data = {
                DOMAIN: {
                    "test_provider": {
                        "provider": "MiniMax",
                        "temperature": 0.5,
                        "top_p": 0.9
                    }
                }
            }

            with patch.object(provider, '_get_system_prompt', return_value="System prompt"):
                result = provider._prepare_vision_data(call)

            assert result["model"] == "MiniMax-M1"
            assert result["max_completion_tokens"] == 1000
            assert len(result["messages"]) == 2  # system + user
            assert result["messages"][0]["role"] == "system"
            assert result["messages"][1]["role"] == "user"

    def test_minimax_prepare_text_data(self, mock_hass_with_session):
        """Test MiniMax provider prepares text data correctly."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )
            call = Mock()
            call.max_tokens = 1000
            call.message = "Generate a title"
            call.provider = "test_provider"

            mock_hass_with_session.data = {
                DOMAIN: {
                    "test_provider": {
                        "provider": "MiniMax",
                        "temperature": 0.5,
                        "top_p": 0.9
                    }
                }
            }

            with patch.object(provider, '_get_title_prompt', return_value="Title prompt"):
                result = provider._prepare_text_data(call)

            assert result["model"] == "MiniMax-M1"
            assert result["max_completion_tokens"] == 1000
            assert len(result["messages"]) == 2

    def test_minimax_default_model(self, mock_hass_with_session):
        """Test MiniMax default model is correctly mapped."""
        from custom_components.llmvision.const import DEFAULT_MINIMAX_MODEL

        mock_hass_with_session.data = {
            DOMAIN: {
                "minimax_entry": {
                    "provider": "MiniMax"
                }
            }
        }

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            request = Request(mock_hass_with_session, "test", 1000, 0.5)
            result = request.get_default_model("minimax_entry")
            assert result == DEFAULT_MINIMAX_MODEL

    @pytest.mark.asyncio
    async def test_minimax_make_request(self, mock_hass_with_session):
        """Test MiniMax provider makes request and parses response."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )

            mock_response = {
                "choices": [
                    {
                        "message": {
                            "content": "A person walking a dog in the park."
                        }
                    }
                ]
            }

            with patch.object(provider, '_post', new_callable=AsyncMock, return_value=mock_response):
                result = await provider._make_request({"model": "MiniMax-M1", "messages": []})

            assert result == "A person walking a dog in the park."

    @pytest.mark.asyncio
    async def test_minimax_validate_success(self, mock_hass_with_session):
        """Test MiniMax provider validation succeeds."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "valid_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )

            mock_response = {"choices": [{"message": {"content": "Hi"}}]}

            with patch.object(provider, '_post', new_callable=AsyncMock, return_value=mock_response):
                await provider.validate()

    @pytest.mark.asyncio
    async def test_minimax_validate_empty_key(self, mock_hass_with_session):
        """Test MiniMax provider validation fails with empty key."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": ""}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )

            with pytest.raises(ServiceValidationError):
                await provider.validate()

    def test_minimax_vision_data_with_structured_output(self, mock_hass_with_session):
        """Test MiniMax prepares vision data with JSON schema structured output."""
        from custom_components.llmvision.providers import ProviderFactory

        config = {"api_key": "test_key"}

        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            provider = ProviderFactory.create(
                mock_hass_with_session,
                "MiniMax",
                config,
                "MiniMax-M1"
            )
            call = Mock()
            call.max_tokens = 1000
            call.base64_images = ["base64_image_data"]
            call.filenames = ["test.jpg"]
            call.message = "Extract data"
            call.provider = "test_provider"
            call.response_format = "json"
            call.structure = '{"type": "object", "properties": {"count": {"type": "integer"}}}'
            call.use_memory = False

            mock_hass_with_session.data = {
                DOMAIN: {
                    "test_provider": {
                        "provider": "MiniMax",
                        "temperature": 0.5,
                        "top_p": 0.9
                    }
                }
            }

            with patch.object(provider, '_get_system_prompt', return_value="System prompt"):
                result = provider._prepare_vision_data(call)

            assert "response_format" in result
            assert result["response_format"]["type"] == "json_schema"
            assert result["response_format"]["json_schema"]["strict"] is True
