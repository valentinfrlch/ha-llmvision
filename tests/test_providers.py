"""Comprehensive unit tests for providers.py module."""

import json
import pytest
import base64
from types import SimpleNamespace
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
from homeassistant.exceptions import ServiceValidationError
from custom_components.llmvision.providers import (
    Request,
    Provider,
    OpenAI,
    AzureOpenAI,
    Anthropic,
    Google,
    Groq,
    LocalAI,
    Ollama,
    AWSBedrock,
    ProviderFactory,
)
from custom_components.llmvision.const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_PROVIDER,
    CONF_DEFAULT_MODEL,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_KEEP_ALIVE,
    CONF_CONTEXT_WINDOW,
    CONF_SYSTEM_PROMPT,
    CONF_TITLE_PROMPT,
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_REGION_NAME,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_AZURE_BASE_URL,
    CONF_AZURE_DEPLOYMENT,
    CONF_AZURE_VERSION,
    CONF_CUSTOM_OPENAI_ENDPOINT,
    CONF_IP_ADDRESS,
    CONF_HTTPS,
    CONF_PORT,
    CONF_THINK,
    CONF_THINKING_BUDGET,
    ENDPOINT_GROQ,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_AZURE_MODEL,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_LOCALAI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TITLE_PROMPT,
)


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
def mock_call():
    """Create a mock call object."""
    call_obj = Mock()
    call_obj.provider = "test_provider"
    call_obj.model = "test-model"
    call_obj.base64_images = ["test_image_base64"]
    call_obj.filenames = ["test.jpg"]
    call_obj.message = "Test message"
    call_obj.max_tokens = 1000
    call_obj.temperature = 0.7
    call_obj.response_format = "text"
    call_obj.generate_title = False
    call_obj.model_is_glimpse = Mock(return_value=False)
    call_obj.use_memory = False
    call_obj.title_field = None
    call_obj.structure = None
    return call_obj


class TestRequest:
    """Test Request class."""

    def test_init(self, mock_hass):
        """Test Request initialization."""
        with patch(
            "custom_components.llmvision.providers.async_get_clientsession"
        ) as mock_session:
            request = Request(mock_hass, "test message", 1000, 0.5)

            assert request.hass == mock_hass
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

    def test_sanitize_data_short_bytes(self):
        """Test sanitize_data with short bytes."""
        data = {"bytes": b"short"}
        result = Request.sanitize_data(data)

        assert result["bytes"] == b"short"

    def test_sanitize_data_nested(self):
        """Test sanitize_data with nested structures."""
        data = {"outer": {"inner": "a" * 500}, "list": ["a" * 500]}
        result = Request.sanitize_data(data)

        assert result["outer"]["inner"] == "<long_string>"
        assert result["list"][0] == "<long_string>"

    def test_sanitize_data_string_with_many_words(self):
        """Test that long strings with many words are not sanitized."""
        # String with more than 50 spaces (400+ chars) but many words should not be sanitized
        data = {"key": " ".join(["word"] * 100)}
        result = Request.sanitize_data(data)

        assert "<long_string>" not in str(result)

    def test_get_provider(self, mock_hass):
        """Test get_provider method."""
        mock_hass.data = {DOMAIN: {"test_uid": {CONF_PROVIDER: "OpenAI"}}}

        result = Request.get_provider(mock_hass, "test_uid")

        assert result == "OpenAI"

    def test_get_provider_not_found(self, mock_hass):
        """Test get_provider when provider not found."""
        mock_hass.data = {}

        result = Request.get_provider(mock_hass, "nonexistent")

        assert result is None

    def test_get_provider_domain_not_in_data(self, mock_hass):
        """Test get_provider when domain not in hass.data."""
        result = Request.get_provider(mock_hass, "any_uid")
        assert result is None

    def test_get_default_model_from_config(self, mock_hass):
        """Test get_default_model from config entry."""
        mock_hass.data = {
            DOMAIN: {
                "test_provider": {
                    CONF_PROVIDER: "OpenAI",
                    CONF_DEFAULT_MODEL: "gpt-4",
                }
            }
        }
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            result = request.get_default_model("test_provider")

            assert result == "gpt-4"

    def test_get_default_model_fallback_openai(self, mock_hass):
        """Test get_default_model fallback to OpenAI default."""
        mock_hass.data = {DOMAIN: {"test_provider": {CONF_PROVIDER: "OpenAI"}}}
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            result = request.get_default_model("test_provider")

            assert result == DEFAULT_OPENAI_MODEL

    def test_get_default_model_fallback_anthropic(self, mock_hass):
        """Test get_default_model fallback to Anthropic default."""
        mock_hass.data = {DOMAIN: {"test_provider": {CONF_PROVIDER: "Anthropic"}}}
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            result = request.get_default_model("test_provider")

            assert result == DEFAULT_ANTHROPIC_MODEL

    def test_get_default_model_invalid_provider(self, mock_hass):
        """Test get_default_model with invalid provider."""
        mock_hass.data = {DOMAIN: {"test_provider": {CONF_PROVIDER: "InvalidProvider"}}}
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            result = request.get_default_model("test_provider")

            assert result is None

    def test_add_frame(self, mock_hass):
        """Test add_frame method."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            request.add_frame("base64_image_data", "test_filename")

            assert len(request.base64_images) == 1
            assert request.base64_images[0] == "base64_image_data"
            assert request.filenames[0] == "test_filename"

    def test_add_multiple_frames(self, mock_hass):
        """Test adding multiple frames."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            request.add_frame("img1", "file1.jpg")
            request.add_frame("img2", "file2.jpg")

            assert len(request.base64_images) == 2
            assert len(request.filenames) == 2

    def test_heal_json_valid_json(self, mock_hass):
        """Test heal_json with valid JSON."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            valid_json = '{"key": "value"}'
            result = request.heal_json(valid_json)

            assert result == valid_json

    def test_heal_json_unterminated_string(self, mock_hass):
        """Test heal_json fixes unterminated string values."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            broken = '{"title":"Front Door","description":"Person at door}'
            healed = request.heal_json(broken)
            parsed = json.loads(healed)

            assert parsed["title"] == "Front Door"
            assert parsed["description"] == "Person at door"

    def test_heal_json_unterminated_string_and_brackets(self, mock_hass):
        """Test heal_json fixes unterminated string and missing brackets."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            broken = '{"title": "No activity", "description": "No people, vehicles, or animals are present'
            healed = request.heal_json(broken)
            parsed = json.loads(healed)

            assert parsed["title"] == "No activity"
            assert (
                parsed["description"] == "No people, vehicles, or animals are present"
            )

    def test_heal_json_unescaped_inner_quotes(self, mock_hass):
        """Test heal_json escapes inner quotes in string values."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            broken = '{"description":"height is 5\\"9 and moving","ok":true}'
            healed = request.heal_json(broken)
            parsed = json.loads(healed)

            assert "height is 5" in parsed["description"]
            assert parsed["ok"] is True

    def test_heal_json_balances_open_containers(self, mock_hass):
        """Test heal_json closes missing brackets/braces."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            broken = '{"events":[{"name":"door"}'
            healed = request.heal_json(broken)
            parsed = json.loads(healed)

            assert isinstance(parsed["events"], list)
            assert parsed["events"][0]["name"] == "door"

    def test_heal_json_non_string(self, mock_hass):
        """Test heal_json with non-string input."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            result = request.heal_json(123)

            assert result == 123

    def test_validate_success(self, mock_hass, mock_call):
        """Test validate succeeds with valid data."""
        mock_hass.data = {DOMAIN: {"test_provider": {CONF_PROVIDER: "OpenAI"}}}
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            # Should not raise
            request.validate(mock_call)

    def test_validate_no_images(self, mock_hass, mock_call):
        """Test validate raises error when no images provided."""
        mock_call.base64_images = []
        mock_hass.data = {DOMAIN: {"test_provider": {CONF_PROVIDER: "OpenAI"}}}
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            with pytest.raises(ServiceValidationError):
                request.validate(mock_call)

    def test_validate_groq_multiple_images(self, mock_hass, mock_call):
        """Test validate raises error for Groq with multiple images."""
        mock_call.base64_images = ["img1", "img2"]
        mock_hass.data = {DOMAIN: {"test_provider": {CONF_PROVIDER: "Groq"}}}
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            with pytest.raises(ServiceValidationError):
                request.validate(mock_call)

    def test_validate_sets_default_model(self, mock_hass, mock_call):
        """Test validate sets default model if not provided."""
        mock_call.model = None
        mock_hass.data = {
            DOMAIN: {
                "test_provider": {
                    CONF_PROVIDER: "OpenAI",
                    CONF_DEFAULT_MODEL: "gpt-4",
                }
            }
        }
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)
            request.validate(mock_call)

            assert mock_call.model == "gpt-4"

    def test_validate_no_provider(self, mock_hass, mock_call):
        """Test validate raises error when provider not configured."""
        mock_call.provider = None
        mock_hass.data = {DOMAIN: {}}
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            request = Request(mock_hass, "test", 1000, 0.5)

            with pytest.raises(ServiceValidationError):
                request.validate(mock_call)


class TestProviderBase:
    """Test Provider base class methods."""

    def test_get_system_prompt_default(self, mock_hass):
        """Test _get_system_prompt returns default."""
        mock_hass.data = {DOMAIN: {}}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            result = provider._get_system_prompt()

            assert result == DEFAULT_SYSTEM_PROMPT

    def test_get_system_prompt_from_settings(self, mock_hass):
        """Test _get_system_prompt from Settings entry."""
        custom_prompt = "Custom system prompt"
        mock_hass.data = {
            DOMAIN: {
                "settings_entry": {
                    CONF_PROVIDER: "Settings",
                    CONF_SYSTEM_PROMPT: custom_prompt,
                }
            }
        }

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            result = provider._get_system_prompt()

            assert result == custom_prompt

    def test_get_title_prompt_default(self, mock_hass):
        """Test _get_title_prompt returns default."""
        mock_hass.data = {DOMAIN: {}}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            result = provider._get_title_prompt()

            assert result == DEFAULT_TITLE_PROMPT

    def test_get_request_url_appends_chat_completions_for_base_url(self, mock_hass_with_session):
        """Test Custom OpenAI base URLs are converted to chat completions endpoints."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            openai = OpenAI(
                mock_hass_with_session,
                "test_api_key",
                "gpt-4",
                endpoint={"base_url": "https://example.test/v1/"},
            )

            assert openai._get_request_url() == "https://example.test/v1/chat/completions"

    def test_get_request_url_keeps_full_chat_completions_endpoint(self, mock_hass_with_session):
        """Test full Custom OpenAI endpoint URLs remain unchanged."""
        with patch('custom_components.llmvision.providers.async_get_clientsession'):
            openai = OpenAI(
                mock_hass_with_session,
                "test_api_key",
                "gpt-4",
                endpoint={"base_url": "https://example.test/v1/chat/completions"},
            )

            assert openai._get_request_url() == "https://example.test/v1/chat/completions"

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
    def test_get_title_prompt_from_settings(self, mock_hass):
        """Test _get_title_prompt from Settings entry."""
        custom_prompt = "Custom title prompt"
        mock_hass.data = {
            DOMAIN: {
                "settings_entry": {
                    CONF_PROVIDER: "Settings",
                    CONF_TITLE_PROMPT: custom_prompt,
                }
            }
        }

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            result = provider._get_title_prompt()

            assert result == custom_prompt

    def test_resolve_request_timeout_default(self, mock_hass):
        """Test _resolve_request_timeout returns default."""
        mock_hass.data = {DOMAIN: {}}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")

            assert provider.request_timeout == 60

    def test_resolve_request_timeout_from_settings(self, mock_hass):
        """Test _resolve_request_timeout from settings."""
        mock_hass.data = {
            DOMAIN: {
                "settings": {
                    CONF_PROVIDER: "Settings",
                    "request_timeout": "120",
                }
            }
        }

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            return_code = provider._resolve_request_timeout()

            assert return_code == 120

    def test_resolve_request_timeout_invalid_value(self, mock_hass):
        """Test _resolve_request_timeout with invalid value falls back to default."""
        mock_hass.data = {
            DOMAIN: {
                "settings": {
                    CONF_PROVIDER: "Settings",
                    "request_timeout": "invalid",
                }
            }
        }

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            result = provider._resolve_request_timeout()

            assert result == 60

    def test_supports_structured_output_default(self, mock_hass):
        """Test supports_structured_output default implementation."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            assert provider.supports_structured_output() is True

    def test_get_default_parameters(self, mock_hass, mock_call):
        """Test _get_default_parameters method."""
        mock_hass.data = {
            DOMAIN: {
                "test_provider": {
                    CONF_TEMPERATURE: 0.8,
                    CONF_TOP_P: 0.95,
                    CONF_KEEP_ALIVE: 10,
                    CONF_CONTEXT_WINDOW: 4096,
                }
            }
        }
        mock_call.model_is_glimpse = Mock(return_value=False)

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            result = provider._get_default_parameters(mock_call)

            assert result["temperature"] == 0.8
            assert result["top_p"] == 0.95
            assert result["keep_alive"] == 10
            assert result["context_window"] == 4096

    def test_get_default_parameters_glimpse_model(self, mock_hass, mock_call):
        """Test _get_default_parameters for Glimpse model."""
        mock_hass.data = {
            DOMAIN: {
                "test_provider": {
                    CONF_TEMPERATURE: 0.8,
                    CONF_TOP_P: 0.95,
                }
            }
        }
        mock_call.model_is_glimpse = Mock(return_value=True)

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = OpenAI(mock_hass, "test_key", "gpt-4")
            result = provider._get_default_parameters(mock_call)

            assert result["temperature"] == 0.2
            assert result["top_p"] == 0.95


class TestOpenAI:
    """Test OpenAI provider class."""

    def test_init(self, mock_hass):
        """Test OpenAI initialization."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            openai = OpenAI(mock_hass, "test_api_key", "gpt-4")

            assert openai.api_key == "test_api_key"
            assert openai.model == "gpt-4"
            assert openai.hass == mock_hass

    def test_supports_structured_output(self, mock_hass):
        """Test supports_structured_output returns True."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            openai = OpenAI(mock_hass, "test_api_key", "gpt-4")

            assert openai.supports_structured_output() is True

    def test_generate_headers(self, mock_hass):
        """Test _generate_headers method."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            openai = OpenAI(mock_hass, "test_api_key", "gpt-4")

            headers = openai._generate_headers()

            assert headers["Authorization"] == "Bearer test_api_key"
            assert headers["Content-type"] == "application/json"

    def test_model_supports_thinking_gpt5(self, mock_hass):
        """Test _model_supports_thinking for gpt-5."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            openai = OpenAI(mock_hass, "test_api_key", "gpt-5.4")

            result = openai._model_supports_thinking("high")

            assert result == "high"

    def test_model_supports_thinking_gpt4(self, mock_hass):
        """Test _model_supports_thinking returns False for gpt-4."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            openai = OpenAI(mock_hass, "test_api_key", "gpt-4")

            result = openai._model_supports_thinking("high")

            assert result is False


class TestAzureOpenAI:
    """Test AzureOpenAI provider class."""

    def test_init(self, mock_hass):
        """Test AzureOpenAI initialization."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            endpoint = {
                "base_url": "https://{base_url}.openai.azure.com/v1",
                "endpoint": "test.openai.azure.com",
                "deployment": "test-deployment",
                "api_version": "2024-02-01",
            }
            azure = AzureOpenAI(mock_hass, "test_api_key", "gpt-4", endpoint=endpoint)

            assert azure.api_key == "test_api_key"
            assert azure.model == "gpt-4"
            assert azure.endpoint["deployment"] == "test-deployment"

    def test_supports_structured_output(self, mock_hass):
        """Test AzureOpenAI supports structured output."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            azure = AzureOpenAI(
                mock_hass,
                "test_api_key",
                "gpt-4",
                endpoint={
                    "base_url": "test",
                    "endpoint": "test",
                    "deployment": "test",
                    "api_version": "2024-02-01",
                },
            )

            assert azure.supports_structured_output() is True

    def test_generate_headers(self, mock_hass):
        """Test AzureOpenAI _generate_headers method."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            azure = AzureOpenAI(
                mock_hass,
                "test_api_key",
                "gpt-4",
                endpoint={
                    "base_url": "test",
                    "endpoint": "test",
                    "deployment": "test",
                    "api_version": "2024-02-01",
                },
            )

            headers = azure._generate_headers()

            assert headers["api-key"] == "test_api_key"
            assert headers["Content-type"] == "application/json"

    def test_uses_completion_tokens_gpt5(self, mock_hass):
        """Test _uses_completion_tokens for gpt-5."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            azure = AzureOpenAI(
                mock_hass,
                "test_api_key",
                "gpt-5",
                endpoint={
                    "base_url": "test",
                    "endpoint": "test",
                    "deployment": "test",
                    "api_version": "2024-02-01",
                },
            )

            assert azure._uses_completion_tokens() is True

    def test_uses_completion_tokens_gpt4(self, mock_hass):
        """Test _uses_completion_tokens for gpt-4."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            azure = AzureOpenAI(
                mock_hass,
                "test_api_key",
                "gpt-4",
                endpoint={
                    "base_url": "test",
                    "endpoint": "test",
                    "deployment": "test",
                    "api_version": "2024-02-01",
                },
            )

            assert azure._uses_completion_tokens() is False


class TestAnthropic:
    """Test Anthropic provider class."""

    def test_init(self, mock_hass):
        """Test Anthropic initialization."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            anthropic = Anthropic(mock_hass, "test_api_key", "claude-3")

            assert anthropic.api_key == "test_api_key"
            assert anthropic.model == "claude-3"

    def test_supports_structured_output(self, mock_hass):
        """Test Anthropic supports structured output."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            anthropic = Anthropic(mock_hass, "test_api_key", "claude-3")

            assert anthropic.supports_structured_output() is True

    def test_generate_headers(self, mock_hass):
        """Test Anthropic _generate_headers method."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            anthropic = Anthropic(mock_hass, "test_api_key", "claude-3")

            headers = anthropic._generate_headers()

            assert headers["x-api-key"] == "test_api_key"
            assert headers["content-type"] == "application/json"
            assert "anthropic-version" in headers


class TestGoogle:
    """Test Google provider class."""

    def test_init(self, mock_hass):
        """Test Google initialization."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            google = Google(mock_hass, "test_api_key", "gemini-pro")

            assert google.api_key == "test_api_key"
            assert google.model == "gemini-pro"

    def test_supports_structured_output(self, mock_hass):
        """Test Google supports structured output."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            google = Google(mock_hass, "test_api_key", "gemini-pro")

            assert google.supports_structured_output() is True

    def test_generate_headers(self, mock_hass):
        """Test Google _generate_headers method."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            google = Google(mock_hass, "test_api_key", "gemini-pro")

            headers = google._generate_headers()

            assert headers["content-type"] == "application/json"

    def test_model_supports_thinking(self, mock_hass):
        """Test _model_supports_thinking for gemini-2.5."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            google = Google(mock_hass, "test_api_key", "gemini-2.5-pro")

            assert google._model_supports_thinking() is True

    def test_model_does_not_support_thinking(self, mock_hass):
        """Test _model_supports_thinking for older models."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            google = Google(mock_hass, "test_api_key", "gemini-pro")

            assert google._model_supports_thinking() is False


class TestGroq:
    """Test Groq provider class."""

    def test_init(self, mock_hass):
        """Test Groq initialization."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            groq = Groq(mock_hass, "test_api_key", "mixtral-8x7b")

            assert groq.api_key == "test_api_key"
            assert groq.model == "mixtral-8x7b"

    def test_supports_structured_output(self, mock_hass):
        """Test Groq supports structured output."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            groq = Groq(mock_hass, "test_api_key", "mixtral-8x7b")

            assert groq.supports_structured_output() is True

    def test_generate_headers(self, mock_hass):
        """Test Groq _generate_headers method."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            groq = Groq(mock_hass, "test_api_key", "mixtral-8x7b")

            headers = groq._generate_headers()

            assert headers["Authorization"] == "Bearer test_api_key"
            assert headers["Content-type"] == "application/json"


class TestLocalAI:
    """Test LocalAI provider class."""

    def test_init(self, mock_hass):
        """Test LocalAI initialization."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            endpoint = {
                "ip_address": "localhost",
                "port": "8080",
                "https": False,
            }
            localai = LocalAI(mock_hass, "", "llava", endpoint=endpoint)

            assert localai.model == "llava"
            assert localai.endpoint["ip_address"] == "localhost"

    def test_supports_structured_output(self, mock_hass):
        """Test LocalAI supports structured output."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            localai = LocalAI(
                mock_hass,
                "",
                "llava",
                endpoint={"ip_address": "localhost", "port": "8080", "https": False},
            )

            assert localai.supports_structured_output() is True


class TestOllama:
    """Test Ollama provider class."""

    def test_init(self, mock_hass):
        """Test Ollama initialization."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            endpoint = {
                "ip_address": "localhost",
                "port": "11434",
                "https": False,
            }
            ollama = Ollama(mock_hass, "", "llava", endpoint=endpoint)

            assert ollama.model == "llava"
            assert ollama.endpoint["ip_address"] == "localhost"

    def test_supports_structured_output(self, mock_hass):
        """Test Ollama supports structured output."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            ollama = Ollama(
                mock_hass,
                "",
                "llava",
                endpoint={
                    "ip_address": "localhost",
                    "port": "11434",
                    "https": False,
                },
            )

            assert ollama.supports_structured_output() is True

    def test_model_supports_thinking_qwen(self, mock_hass):
        """Test _model_supports_thinking for qwen3.5."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            ollama = Ollama(
                mock_hass,
                "",
                "qwen3.5",
                endpoint={
                    "ip_address": "localhost",
                    "port": "11434",
                    "https": False,
                },
            )

            assert ollama._model_supports_thinking() is True

    def test_model_does_not_support_thinking(self, mock_hass):
        """Test _model_supports_thinking for non-thinking models."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            ollama = Ollama(
                mock_hass,
                "",
                "llava",
                endpoint={
                    "ip_address": "localhost",
                    "port": "11434",
                    "https": False,
                },
            )

            assert ollama._model_supports_thinking() is False


class TestAWSBedrock:
    """Test AWSBedrock provider class."""

    def test_init_with_bearer_token(self, mock_hass):
        """Test AWSBedrock initialization with bearer token."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            bedrock = AWSBedrock(
                mock_hass,
                aws_access_key_id="",
                aws_secret_access_key="",
                aws_region_name="us-east-1",
                model="claude-3",
                api_key="bearer_token",
            )

            assert bedrock.api_key == "bearer_token"
            assert bedrock.use_bearer_token is True
            assert bedrock.aws_region == "us-east-1"

    def test_init_with_iam_credentials(self, mock_hass):
        """Test AWSBedrock initialization with IAM credentials."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            bedrock = AWSBedrock(
                mock_hass,
                aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
                aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                aws_region_name="us-west-2",
                model="claude-3",
            )

            assert bedrock.aws_access_key_id == "AKIAIOSFODNN7EXAMPLE"
            assert bedrock.use_bearer_token is False
            assert bedrock.aws_region == "us-west-2"

    def test_supports_structured_output(self, mock_hass):
        """Test AWSBedrock supports structured output."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            bedrock = AWSBedrock(
                mock_hass,
                aws_access_key_id="",
                aws_secret_access_key="",
                aws_region_name="us-east-1",
                model="claude-3",
                api_key="test",
            )

            assert bedrock.supports_structured_output() is True

    def test_generate_headers(self, mock_hass):
        """Test AWSBedrock _generate_headers method."""
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            bedrock = AWSBedrock(
                mock_hass,
                aws_access_key_id="",
                aws_secret_access_key="",
                aws_region_name="us-east-1",
                model="claude-3",
                api_key="test_token",
            )

            headers = bedrock._generate_headers()

            assert headers["Authorization"] == "Bearer test_token"
            assert headers["Content-type"] == "application/json"


class TestProviderFactory:
    """Test ProviderFactory class."""

    def test_create_openai(self, mock_hass):
        """Test ProviderFactory creates OpenAI provider."""
        config = {CONF_API_KEY: "test_key"}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(mock_hass, "OpenAI", config, "gpt-4")

            assert isinstance(provider, OpenAI)
            assert provider.model == "gpt-4"

    def test_create_azure(self, mock_hass):
        """Test ProviderFactory creates AzureOpenAI provider."""
        config = {
            CONF_API_KEY: "test_key",
            "azure_base_url": "https://test.openai.azure.com/",
            "azure_deployment": "test-deployment",
            "azure_version": "2024-02-01",
        }

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(mock_hass, "Azure", config, "gpt-4")

            assert isinstance(provider, AzureOpenAI)

    def test_create_anthropic(self, mock_hass):
        """Test ProviderFactory creates Anthropic provider."""
        config = {CONF_API_KEY: "test_key"}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(
                mock_hass, "Anthropic", config, "claude-3"
            )

            assert isinstance(provider, Anthropic)

    def test_create_google(self, mock_hass):
        """Test ProviderFactory creates Google provider."""
        config = {CONF_API_KEY: "test_key"}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(mock_hass, "Google", config, "gemini-pro")

            assert isinstance(provider, Google)

    def test_create_groq(self, mock_hass):
        """Test ProviderFactory creates Groq provider."""
        config = {CONF_API_KEY: "test_key"}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(mock_hass, "Groq", config, "mixtral-8x7b")

            assert isinstance(provider, Groq)

    def test_create_localai(self, mock_hass):
        """Test ProviderFactory creates LocalAI provider."""
        config = {"ip_address": "localhost", "port": "8080", "https": False}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(mock_hass, "LocalAI", config, "llava")

            assert isinstance(provider, LocalAI)

    def test_create_ollama(self, mock_hass):
        """Test ProviderFactory creates Ollama provider."""
        config = {"ip_address": "localhost", "port": "11434", "https": False}

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(mock_hass, "Ollama", config, "llava")

            assert isinstance(provider, Ollama)

    def test_create_custom_openai(self, mock_hass):
        """Test ProviderFactory creates Custom OpenAI provider."""
        config = {
            CONF_API_KEY: "test_key",
            "custom_openai_endpoint": "https://custom.example.com/v1/chat/completions",
        }

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(
                mock_hass, "Custom OpenAI", config, "custom-model"
            )

            assert isinstance(provider, OpenAI)

    def test_create_aws_bedrock(self, mock_hass):
        """Test ProviderFactory creates AWS Bedrock provider."""
        config = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_region": "us-east-1",
        }

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(
                mock_hass, "AWS Bedrock", config, "claude-3"
            )

            assert isinstance(provider, AWSBedrock)

    def test_create_open_webui(self, mock_hass):
        """Test ProviderFactory creates OpenWebUI provider."""
        config = {
            CONF_API_KEY: "test_key",
            "custom_openai_endpoint": "http://localhost:8000/v1/chat/completions",
        }

        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            provider = ProviderFactory.create(
                mock_hass, "Open WebUI", config, "local-model"
            )

            assert isinstance(provider, OpenAI)


@pytest.fixture
def coverage_hass(monkeypatch):
    monkeypatch.setattr(
        "custom_components.llmvision.providers.async_get_clientsession",
        lambda hass: Mock(),
    )
    obj = Mock()
    obj.data = {
        DOMAIN: {
            "provider_openai": {
                CONF_PROVIDER: "OpenAI",
                CONF_API_KEY: "k",
                CONF_DEFAULT_MODEL: "gpt-4o",
                CONF_TEMPERATURE: 0.6,
            },
            "provider_groq": {CONF_PROVIDER: "Groq", CONF_API_KEY: "k"},
            "settings": {
                CONF_PROVIDER: "Settings",
                "fallback_provider": "no_fallback",
                "system_prompt": "system",
                "title_prompt": "title",
                "request_timeout": "30",
            },
        }
    }
    settings_entry = SimpleNamespace(
        data={"provider": "Settings", "fallback_provider": "provider_openai"}
    )
    obj.config_entries = Mock()
    obj.config_entries.async_entries = Mock(return_value=[settings_entry])
    obj.async_add_executor_job = AsyncMock()
    return obj


def make_coverage_call(**overrides):
    call_obj = SimpleNamespace(
        provider="provider_openai",
        model="gpt-4o",
        base64_images=["aW1n"],
        filenames=["cam.jpg"],
        message="hello",
        max_tokens=64,
        temperature=0.5,
        top_p=0.9,
        response_format="text",
        generate_title=False,
        title_field=None,
        structure=None,
        use_memory=False,
        memory=SimpleNamespace(
            title_prompt="tp:",
            _get_memory_images=lambda memory_type: [
                {"type": "text", "text": f"mem-{memory_type}"}
            ],
        ),
    )
    call_obj.model_is_glimpse = lambda: False
    for key, value in overrides.items():
        setattr(call_obj, key, value)
    return call_obj


def make_openai_chat_completion_response(text="ok"):
    return {
        "id": "chatcmpl_test",
        "object": "chat.completion",
        "created": 1735689600,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


def make_anthropic_text_response(text="ok"):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-6",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 12, "output_tokens": 6},
    }


def make_anthropic_tool_use_response(tool_input=None):
    if tool_input is None:
        tool_input = {"a": 1}
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-6",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_test",
                "name": "return_structured_data",
                "input": tool_input,
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 12, "output_tokens": 6},
    }


def make_google_generate_content_response(text="ok"):
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": "STOP",
                "index": 0,
            }
        ],
        "modelVersion": "gemini-2.5-pro",
        "responseId": "resp_test",
    }


class DummyProvider:
    def __init__(
        self,
        response_text="ok",
        title_text="T",
        supports=True,
        fail_vision=False,
        fail_title=False,
    ):
        self.response_text = response_text
        self.title_text = title_text
        self.supports = supports
        self.fail_vision = fail_vision
        self.fail_title = fail_title

    async def vision_request(self, _call):
        if self.fail_vision:
            raise RuntimeError("vision failed")
        return self.response_text

    async def title_request(self, _call):
        if self.fail_title:
            raise RuntimeError("title failed")
        return self.title_text

    def supports_structured_output(self):
        return self.supports


@pytest.mark.anyio
async def test_request_call_structured_json_coverage(monkeypatch, coverage_hass):
    req = Request(coverage_hass, "m", 10, 0.2)
    req.base64_images = ["aW1n"]
    req.filenames = ["f.jpg"]
    call_obj = make_coverage_call(
        response_format="json", structure={"type": "object"}, title_field="name"
    )

    provider = DummyProvider(response_text='{"name":"Hello","x":1}', supports=True)
    monkeypatch.setattr(ProviderFactory, "create", lambda **kwargs: provider)

    result = await req.call(call_obj)

    assert result["title"] == "Hello"
    assert result["structured_response"]["x"] == 1
    assert "response_text" not in result


@pytest.mark.anyio
async def test_request_call_generate_title_and_fallback_coverage(
    monkeypatch, coverage_hass
):
    req = Request(coverage_hass, "m", 10, 0.2)
    req.base64_images = ["aW1n"]
    req.filenames = ["f.jpg"]

    first = DummyProvider(fail_vision=True)
    second = DummyProvider(
        response_text="ok text", title_text="Door!* Title", supports=False
    )

    providers = [first, second]
    monkeypatch.setattr(ProviderFactory, "create", lambda **kwargs: providers.pop(0))

    call_obj = make_coverage_call(
        provider="provider_groq",
        model="mixtral",
        generate_title=True,
        response_format="text",
    )

    result = await req.call(call_obj)

    assert result["title"] == "Door Title"
    assert result["response_text"] == "ok text"


@pytest.mark.anyio
async def test_provider_post_success_and_errors_coverage(coverage_hass):
    provider = OpenAI(coverage_hass, "k", "gpt-4")

    ok_response = Mock(status=200)
    ok_response.json = AsyncMock(return_value={"ok": True})
    provider.session.post = AsyncMock(return_value=ok_response)
    parsed = await provider._post("https://x?key=abc", {"h": "v"}, {"a": 1})
    assert parsed["ok"] is True

    fail_response = Mock(status=400)
    fail_response.text = AsyncMock(return_value='{"error":{"message":"bad"}}')
    provider.session.post = AsyncMock(return_value=fail_response)

    frame = SimpleNamespace(frame=SimpleNamespace(f_locals={"self": provider}))
    with pytest.MonkeyPatch.context() as monkeypatch_ctx:
        monkeypatch_ctx.setattr(
            "custom_components.llmvision.providers.inspect.stack",
            lambda: [None, frame],
        )
        with pytest.raises(ServiceValidationError):
            await provider._post("https://x", {}, {})

    provider.session.post = AsyncMock(side_effect=RuntimeError("down"))
    with pytest.raises(ServiceValidationError):
        await provider._post("https://x", {}, {})


@pytest.mark.anyio
async def test_aws_invoke_bedrock_success_and_error_coverage(coverage_hass):
    provider = AWSBedrock(coverage_hass, "AK", "SK", "us-east-1", "m")

    client = Mock()
    client.converse = Mock(
        return_value={
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "metrics": {"latencyMs": 1},
            "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
            "output": {"message": {"content": [{"text": "ok"}]}},
        }
    )

    coverage_hass.async_add_executor_job = AsyncMock(
        side_effect=[client, client.converse()]
    )
    output = await provider.invoke_bedrock("m", {"messages": [], "inferenceConfig": {}})
    assert "message" in output

    bad = {
        "ResponseMetadata": {"HTTPStatusCode": 400},
        "error": {"message": "bad"},
    }
    coverage_hass.async_add_executor_job = AsyncMock(side_effect=[client, bad])
    frame = SimpleNamespace(frame=SimpleNamespace(f_locals={"self": provider}))
    with pytest.MonkeyPatch.context() as monkeypatch_ctx:
        monkeypatch_ctx.setattr(
            "custom_components.llmvision.providers.inspect.stack",
            lambda: [None, frame],
        )
        with pytest.raises(ServiceValidationError):
            await provider.invoke_bedrock("m", {"messages": [], "inferenceConfig": {}})


@pytest.mark.anyio
async def test_provider_coverage_misc_paths(monkeypatch, coverage_hass):
    original_factory_create = ProviderFactory.create
    req = Request(coverage_hass, "m", 10, 0.2)
    req.base64_images = ["aW1n"]
    req.filenames = ["f.jpg"]

    provider = DummyProvider(response_text='{"title":"A!","description":"D"}')
    monkeypatch.setattr(ProviderFactory, "create", lambda **kwargs: provider)
    call_obj = make_coverage_call()
    call_obj.model_is_glimpse = lambda: True
    result = await req.call(call_obj)
    assert result["title"] == "A"
    assert result["response_text"] == "D"

    with pytest.raises(ServiceValidationError):
        await req.call(make_coverage_call(provider="missing"))

    coverage_hass.data[DOMAIN]["provider_openai"][CONF_PROVIDER] = None
    with pytest.raises(ServiceValidationError):
        await req.call(make_coverage_call())
    coverage_hass.data[DOMAIN]["provider_openai"][CONF_PROVIDER] = "OpenAI"

    with pytest.raises(ServiceValidationError):
        await req.call(make_coverage_call(model=123))

    monkeypatch.setattr(
        ProviderFactory,
        "create",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(ServiceValidationError):
        await req.call(make_coverage_call(model="gpt-4o"))

    monkeypatch.setattr(
        ProviderFactory,
        "create",
        lambda **kwargs: DummyProvider(response_text="not-json", supports=True),
    )
    result = await req.call(
        make_coverage_call(response_format="json", structure={"type": "object"})
    )
    assert result["response_text"] == "not-json"

    monkeypatch.setattr(ProviderFactory, "create", original_factory_create)

    openai = OpenAI(coverage_hass, "k", "gpt-5")
    coverage_hass.data[DOMAIN]["provider_openai"]["reasoning_effort"] = "high"
    payload = openai._prepare_vision_data(
        make_coverage_call(
            response_format="json", structure='{"type":"object"}', use_memory=True
        )
    )
    assert "temperature" not in payload
    assert (
        payload["response_format"]["json_schema"]["schema"]["additionalProperties"]
        is False
    )

    azure = AzureOpenAI(
        coverage_hass,
        "k",
        "gpt-4",
        endpoint={
            "base_url": "https://{base_url}/{deployment}?api-version={api_version}",
            "endpoint": "ep",
            "deployment": "dep",
            "api_version": "2025-01-01",
        },
    )
    assert (
        azure._prepare_vision_data(
            make_coverage_call(
                response_format="json", structure={"type": "object"}, use_memory=True
            )
        )["max_tokens"]
        == 64
    )

    anthropic = Anthropic(coverage_hass, "k", "claude")
    with pytest.raises(ServiceValidationError):
        anthropic._prepare_vision_data(
            make_coverage_call(response_format="json", structure="{")
        )

    google = Google(coverage_hass, "k", "gemini-2.5-pro")
    coverage_hass.data[DOMAIN]["provider_openai"][CONF_THINKING_BUDGET] = 12
    g_payload = google._prepare_vision_data(
        make_coverage_call(
            response_format="json", structure={"type": "object"}, use_memory=True
        )
    )
    assert g_payload["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 12

    groq = Groq(coverage_hass, "k", "llama")
    assert (
        groq._prepare_vision_data(
            make_coverage_call(response_format="json", structure={"type": "object"})
        )["response_format"]["json_schema"]["strict"]
        is False
    )

    localai = LocalAI(
        coverage_hass,
        "",
        "llava",
        endpoint={"ip_address": "127.0.0.1", "port": "8080", "https": False},
    )
    assert (
        localai._prepare_vision_data(
            make_coverage_call(
                response_format="json", structure={"type": "object"}, use_memory=True
            )
        )["response_format"]["json_schema"]["strict"]
        is False
    )

    ollama = Ollama(
        coverage_hass,
        "",
        "qwen3.5",
        endpoint={"ip_address": "127.0.0.1", "port": "11434", "https": False},
    )
    coverage_hass.data[DOMAIN]["provider_openai"][CONF_THINK] = True
    coverage_hass.data[DOMAIN]["provider_openai"][CONF_KEEP_ALIVE] = 8
    coverage_hass.data[DOMAIN]["provider_openai"][CONF_CONTEXT_WINDOW] = 1234
    o_payload = ollama._prepare_vision_data(
        make_coverage_call(
            response_format="json", structure={"type": "object"}, use_memory=True
        )
    )
    assert o_payload["think"] is True

    bedrock = AWSBedrock(coverage_hass, "AK", "SK", "us-east-1", "m")
    b_payload = bedrock._prepare_vision_data(
        make_coverage_call(
            response_format="json", structure={"type": "object"}, use_memory=True
        )
    )
    assert (
        b_payload["toolConfig"]["toolChoice"]["tool"]["name"]
        == "return_structured_data"
    )

    config = {
        CONF_API_KEY: "k",
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_PORT: "8080",
        CONF_HTTPS: False,
        CONF_CUSTOM_OPENAI_ENDPOINT: "http://x/v1/chat/completions",
        CONF_AWS_ACCESS_KEY_ID: "AK",
        CONF_AWS_SECRET_ACCESS_KEY: "SK",
        CONF_AWS_REGION_NAME: "us-east-1",
        CONF_AZURE_BASE_URL: "base",
        CONF_AZURE_DEPLOYMENT: "dep",
        CONF_AZURE_VERSION: "v",
    }
    assert isinstance(
        ProviderFactory.create(coverage_hass, "OpenRouter", config, "m"), OpenAI
    )
    assert isinstance(
        ProviderFactory.create(coverage_hass, "OpenWebUI", config, "m"), OpenAI
    )
    with pytest.raises(ServiceValidationError):
        ProviderFactory.create(coverage_hass, "Nope", config, "m")

    assert ENDPOINT_GROQ


class MinimalProvider(Provider):
    async def _make_request(self, data: dict) -> str:
        return "ok"

    def _prepare_vision_data(self, call) -> dict:
        return {"v": True}

    def _prepare_text_data(self, call) -> dict:
        return {"t": True}

    async def validate(self):
        return None


@pytest.mark.anyio
async def test_provider_vision_title_request_delegate_coverage(coverage_hass):
    provider = MinimalProvider(coverage_hass, "", "m")
    call_obj = make_coverage_call()
    assert await provider.vision_request(vars(call_obj)) == "ok"
    assert await provider.title_request(vars(call_obj)) == "ok"
    assert call_obj.max_tokens == 4096
    assert provider.supports_structured_output() is False


@pytest.mark.anyio
async def test_provider_resolve_error_variants(coverage_hass):
    provider = OpenAI(coverage_hass, "k", "gpt-4")

    anthropic_response = Mock()
    anthropic_response.text = AsyncMock(
        return_value='{"error":{"type":"invalid_request","message":"bad req"}}'
    )
    parsed = await provider._resolve_error(anthropic_response, "anthropic")
    assert parsed == "invalid_request: bad req"

    ollama_response = Mock()
    ollama_response.text = AsyncMock(return_value='{"error":"ollama bad"}')
    parsed = await provider._resolve_error(ollama_response, "ollama")
    assert parsed == "ollama bad"

    generic_response = Mock()
    generic_response.text = AsyncMock(return_value='{"error":{"message":"boom"}}')
    parsed = await provider._resolve_error(generic_response, "openai")
    assert parsed == "boom"


@pytest.mark.anyio
async def test_openai_make_request_and_validate_paths(coverage_hass):
    provider = OpenAI(coverage_hass, "k", "gpt-4")
    provider._post = AsyncMock(return_value=make_openai_chat_completion_response())
    assert await provider._make_request({"x": 1}) == "ok"

    provider._post = AsyncMock(return_value={"choices": []})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    provider._post = AsyncMock(return_value={"choices": ["bad"]})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    provider._post = AsyncMock(return_value={"choices": [{"message": "bad"}]})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    provider._post = AsyncMock(return_value={"choices": [{"message": {}}]})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    provider._post = AsyncMock(return_value={"ok": True})
    await provider.validate()

    provider_no_key = OpenAI(coverage_hass, "", "gpt-4")
    with pytest.raises(ServiceValidationError):
        await provider_no_key.validate()


@pytest.mark.anyio
async def test_azure_make_request_text_prepare_and_validate_paths(coverage_hass):
    provider = AzureOpenAI(
        coverage_hass,
        "k",
        "gpt-5-mini",
        endpoint={
            "base_url": "https://{base_url}/{deployment}?api-version={api_version}",
            "endpoint": "ep",
            "deployment": "dep",
            "api_version": "2025-01-01",
        },
    )
    provider._post = AsyncMock(
        return_value={"choices": [{"message": {"content": "ok"}}]}
    )
    assert await provider._make_request({"x": 1}) == "ok"

    payload = provider._prepare_text_data(
        make_coverage_call(
            response_format="json", structure={"type": "object"}, max_tokens=33
        )
    )
    assert payload["max_completion_tokens"] == 33
    assert "temperature" not in payload
    assert payload["response_format"]["json_schema"]["strict"] is True

    provider._post = AsyncMock(return_value={"ok": True})
    await provider.validate()

    no_key = AzureOpenAI(
        coverage_hass,
        "",
        "gpt-4",
        endpoint={
            "base_url": "https://{base_url}/{deployment}?api-version={api_version}",
            "endpoint": "ep",
            "deployment": "dep",
            "api_version": "2025-01-01",
        },
    )
    with pytest.raises(ServiceValidationError):
        await no_key.validate()


@pytest.mark.anyio
async def test_anthropic_make_request_prepare_text_and_validate_paths(coverage_hass):
    provider = Anthropic(coverage_hass, "k", "claude-3")

    provider._post = AsyncMock(return_value=make_anthropic_text_response())
    assert await provider._make_request({"x": 1}) == "ok"

    provider._post = AsyncMock(return_value=make_anthropic_tool_use_response())
    assert await provider._make_request({"x": 1}) == '{"a": 1}'

    provider._post = AsyncMock(return_value={"content": []})
    assert await provider._make_request({"x": 1}) == ""

    payload = provider._prepare_text_data(
        make_coverage_call(response_format="json", structure={"type": "object"})
    )
    assert payload["tool_choice"]["name"] == "return_structured_data"

    provider._post = AsyncMock(return_value={"ok": True})
    await provider.validate()

    no_key = Anthropic(coverage_hass, "", "claude-3")
    with pytest.raises(ServiceValidationError):
        await no_key.validate()


@pytest.mark.anyio
async def test_google_make_request_prepare_text_and_validate_paths(coverage_hass):
    provider = Google(coverage_hass, "k", "gemini-2.5-pro")

    provider._post = AsyncMock(return_value=make_google_generate_content_response())
    assert await provider._make_request({"x": 1}) == "ok"

    provider._post = AsyncMock(return_value={"candidates": []})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    provider._post = AsyncMock(return_value={"candidates": [{}]})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    with pytest.raises(ServiceValidationError):
        provider._prepare_text_data(
            make_coverage_call(response_format="json", structure="{")
        )

    provider._post = AsyncMock(return_value={"ok": True})
    await provider.validate()

    no_key = Google(coverage_hass, "", "gemini-pro")
    with pytest.raises(ServiceValidationError):
        await no_key.validate()


@pytest.mark.anyio
async def test_groq_make_request_prepare_text_and_validate_paths(coverage_hass):
    provider = Groq(coverage_hass, "k", "llama-3.2")

    provider._post = AsyncMock(
        return_value={"choices": [{"message": {"content": "ok"}}]}
    )
    assert await provider._make_request({"x": 1}) == "ok"

    provider._post = AsyncMock(return_value={"choices": []})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    payload = provider._prepare_text_data(
        make_coverage_call(response_format="json", structure={"type": "object"})
    )
    assert payload["response_format"]["json_schema"]["strict"] is False

    provider._post = AsyncMock(return_value={"ok": True})
    await provider.validate()

    no_key = Groq(coverage_hass, "", "llama")
    with pytest.raises(ServiceValidationError):
        await no_key.validate()


@pytest.mark.anyio
async def test_localai_make_request_prepare_text_and_validate_paths(
    coverage_hass, monkeypatch
):
    provider = LocalAI(
        coverage_hass,
        "",
        "llava",
        endpoint={"ip_address": "127.0.0.1", "port": "8080", "https": False},
    )
    provider._post = AsyncMock(
        return_value={"choices": [{"message": {"content": "ok"}}]}
    )
    assert await provider._make_request({"x": 1}) == "ok"

    provider._post = AsyncMock(return_value={"choices": []})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    with pytest.raises(ServiceValidationError):
        provider._prepare_text_data(
            make_coverage_call(response_format="json", structure="{")
        )

    session = Mock()
    session.get = AsyncMock(return_value=SimpleNamespace(status=200))
    monkeypatch.setattr(
        "custom_components.llmvision.providers.async_get_clientsession",
        lambda hass: session,
    )
    await provider.validate()

    session.get = AsyncMock(return_value=SimpleNamespace(status=500))
    with pytest.raises(ServiceValidationError):
        await provider.validate()


@pytest.mark.anyio
async def test_ollama_make_request_prepare_text_and_validate_paths(
    coverage_hass, monkeypatch
):
    provider = Ollama(
        coverage_hass,
        "",
        "qwen3.5",
        endpoint={"ip_address": "127.0.0.1", "port": "11434", "https": False},
    )
    provider._post = AsyncMock(return_value={"message": {"content": "ok"}})
    assert await provider._make_request({"x": 1}) == "ok"

    provider._post = AsyncMock(return_value={"message": {}})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})

    with pytest.raises(ServiceValidationError):
        provider._prepare_text_data(
            make_coverage_call(response_format="json", structure="{")
        )

    session = Mock()
    session.get = AsyncMock(return_value=SimpleNamespace(status=200))
    monkeypatch.setattr(
        "custom_components.llmvision.providers.async_get_clientsession",
        lambda hass: session,
    )
    await provider.validate()

    session.get = AsyncMock(side_effect=RuntimeError("down"))
    with pytest.raises(ServiceValidationError):
        await provider.validate()


@pytest.mark.anyio
async def test_aws_make_request_paths_and_prepare_text_errors(coverage_hass):
    bearer = AWSBedrock(
        coverage_hass,
        aws_access_key_id="",
        aws_secret_access_key="",
        aws_region_name="us-east-1",
        model="m",
        api_key="token",
    )
    bearer._post = AsyncMock(
        return_value={"output": {"message": {"content": [{"text": "ok"}]}}}
    )
    assert await bearer._make_request({"x": 1}) == "ok"

    bearer._post = AsyncMock(
        return_value={
            "output": {"message": {"content": [{"toolUse": {"input": {"k": "v"}}}]}}
        }
    )
    assert await bearer._make_request({"x": 1}) == '{"k": "v"}'

    bearer._post = AsyncMock(return_value={"output": {"message": {"content": []}}})
    assert await bearer._make_request({"x": 1}) == ""

    iam = AWSBedrock(coverage_hass, "AK", "SK", "us-east-1", "m")
    iam.invoke_bedrock = AsyncMock(
        return_value={"message": {"content": [{"text": "ok iam"}]}}
    )
    assert await iam._make_request({"x": 1}) == "ok iam"

    iam.invoke_bedrock = AsyncMock(return_value={"message": {"content": [{"bad": 1}]}})
    assert await iam._make_request({"x": 1}) == ""

    with pytest.raises(ServiceValidationError):
        bearer._prepare_text_data(
            make_coverage_call(response_format="json", structure="{")
        )


@pytest.mark.anyio
async def test_provider_factory_openwebui_alias_and_request_fallback_title_error(
    monkeypatch, coverage_hass
):
    config = {
        CONF_API_KEY: "k",
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_PORT: "3000",
        CONF_HTTPS: True,
    }
    provider = ProviderFactory.create(coverage_hass, "Open WebUI", config, "m")
    assert isinstance(provider, OpenAI)
    assert provider.endpoint["base_url"].startswith("https://")

    req = Request(coverage_hass, "m", 10, 0.2)
    req.base64_images = ["aW1n"]
    req.filenames = ["f.jpg"]
    broken_title_provider = DummyProvider(
        response_text="body",
        title_text="ignored",
        supports=False,
        fail_title=True,
    )
    monkeypatch.setattr(
        ProviderFactory,
        "create",
        lambda **kwargs: broken_title_provider,
    )
    result = await req.call(
        make_coverage_call(generate_title=True, response_format="text")
    )
    assert result["title"] == "Event Detected"
    assert result["response_text"] == "body"


def test_request_extra_provider_and_model_branches(mock_hass):
    mock_hass.data = {DOMAIN: {"uid": {}}}
    with patch("custom_components.llmvision.providers.async_get_clientsession"):
        request = Request(mock_hass, "m", 10, 0.1)
        assert Request.get_provider(mock_hass, "missing") is None
        assert request.get_default_model("uid") is None


@pytest.mark.anyio
async def test_request_call_error_and_title_fallback_branches(
    monkeypatch, coverage_hass
):
    req = Request(coverage_hass, "m", 10, 0.2)
    req.base64_images = ["aW1n"]
    req.filenames = ["f.jpg"]

    # Vision failure without fallback configured hits default error text.
    coverage_hass.config_entries.async_entries.return_value = [
        SimpleNamespace(
            data={"provider": "Settings", "fallback_provider": "no_fallback"}
        )
    ]
    monkeypatch.setattr(
        ProviderFactory,
        "create",
        lambda **kwargs: DummyProvider(fail_vision=True),
    )
    result = await req.call(make_coverage_call())
    assert result["response_text"].startswith("Couldn't generate content")

    # Glimpse parse failure exercises nested exception handling.
    monkeypatch.setattr(
        ProviderFactory,
        "create",
        lambda **kwargs: DummyProvider(response_text="not-json", supports=False),
    )
    result = await req.call(
        make_coverage_call(
            model="glimpse-v1",
            response_format="text",
            generate_title=False,
        )
    )
    assert result["response_text"] == "not-json"

    # Invalid JSON for title extraction path keeps title unset.
    result = await req.call(
        make_coverage_call(response_format="json", title_field="title")
    )
    assert "title" not in result

    # Title generation fallback to another provider hits recursive title fallback branch.
    coverage_hass.config_entries.async_entries.return_value = [
        SimpleNamespace(
            data={"provider": "Settings", "fallback_provider": "provider_openai"}
        )
    ]
    providers = [
        DummyProvider(response_text="body1", fail_title=True, supports=False),
        DummyProvider(response_text="body2", title_text="Title#2", supports=False),
    ]
    monkeypatch.setattr(ProviderFactory, "create", lambda **kwargs: providers.pop(0))
    result = await req.call(
        make_coverage_call(
            provider="provider_groq", generate_title=True, response_format="text"
        )
    )
    assert result["title"] == "Title2"
    assert result["response_text"] == "body2"


def test_heal_json_extra_branches(mock_hass):
    with patch("custom_components.llmvision.providers.async_get_clientsession"):
        request = Request(mock_hass, "m", 10, 0.2)
        # Exercise escaped and inner quote handling branches.
        healed = request.heal_json('{"x":"a\\\\b and 5"9"}')
        assert isinstance(healed, str)
        # Unrecoverable remains unchanged.
        broken = '{"a": [}'
        assert request.heal_json(broken) == broken


@pytest.mark.anyio
async def test_provider_base_additional_paths(coverage_hass):
    provider = MinimalProvider(coverage_hass, "", "m")

    # Execute abstract pass lines directly for full branch coverage accounting.
    assert Provider._prepare_vision_data(provider, {}) is None
    assert Provider._prepare_text_data(provider, {}) is None
    assert await Provider._make_request(provider, {}) is None
    assert await Provider.validate(provider) is None

    obj_call = make_coverage_call()
    assert await provider.title_request(obj_call) == "ok"
    assert obj_call.max_tokens == 4096

    bad_response = Mock()
    bad_response.text = AsyncMock(side_effect=RuntimeError("boom"))
    assert await provider._resolve_error(bad_response, "openai") == "Unknown error"

    # Non-JSON string path then dict provider fallback path.
    txt_response = Mock()
    txt_response.text = AsyncMock(return_value="not-json")
    assert await provider._resolve_error(txt_response, "openai") == "Unknown error"
    assert await provider._resolve_error({"errorMessage": "E"}, "openai") == "E"


@pytest.mark.anyio
async def test_openai_specific_missing_branches(monkeypatch, coverage_hass):
    provider = OpenAI(coverage_hass, "k", "gpt-5.4")
    coverage_hass.data[DOMAIN]["provider_openai"]["reasoning_effort"] = "xhigh"

    call_obj = make_coverage_call(
        response_format="json", structure="{", use_memory=False
    )
    payload = provider._prepare_vision_data(call_obj)
    assert payload["reasoning_effort"] == "xhigh"
    assert "response_format" not in payload

    text_payload = provider._prepare_text_data(make_coverage_call())
    assert text_payload["max_completion_tokens"] == 64

    provider.endpoint = "https://openrouter.ai/api/v1/chat/completions"
    provider._post = AsyncMock(return_value=make_openai_chat_completion_response())
    with patch("builtins.print"):
        assert await provider._make_request({"x": 1}) == "ok"

    provider.endpoint = 123
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})


@pytest.mark.anyio
async def test_azure_missing_branches(coverage_hass):
    provider = AzureOpenAI(
        coverage_hass,
        "k",
        "gpt-5",
        endpoint={
            "base_url": "https://{base_url}/{deployment}?api-version={api_version}",
            "endpoint": "ep",
            "deployment": "dep",
            "api_version": "2025-01-01",
        },
    )
    p = provider._prepare_vision_data(
        make_coverage_call(response_format="json", structure="{")
    )
    assert p["max_completion_tokens"] == 64
    assert "response_format" not in p

    p2 = provider._prepare_text_data(
        make_coverage_call(response_format="json", structure="{")
    )
    assert p2["max_completion_tokens"] == 64

    provider._post = AsyncMock(return_value={"choices": [{}]})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})
    provider._post = AsyncMock(return_value={"choices": [{"message": "bad"}]})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})
    provider._post = AsyncMock(return_value={"choices": [{"message": {}}]})
    with pytest.raises(ServiceValidationError):
        await provider._make_request({})


@pytest.mark.anyio
async def test_anthropic_google_groq_localai_ollama_aws_extra_branches(coverage_hass):
    # Anthropic vision/image/memory/tool branch.
    anthropic = Anthropic(coverage_hass, "k", "claude")
    a_payload = anthropic._prepare_vision_data(
        make_coverage_call(
            response_format="json", structure={"type": "object"}, use_memory=True
        )
    )
    assert a_payload["tools"][0]["name"] == "return_structured_data"
    with pytest.raises(ServiceValidationError):
        anthropic._prepare_text_data(
            make_coverage_call(response_format="json", structure="{")
        )

    google = Google(coverage_hass, "k", "gemini-2.5-pro")
    coverage_hass.data[DOMAIN]["provider_openai"][CONF_THINKING_BUDGET] = 7
    g_text = google._prepare_text_data(
        make_coverage_call(response_format="json", structure={"type": "object"})
    )
    assert g_text["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 7
    assert g_text["generationConfig"]["response_mime_type"] == "application/json"
    with pytest.raises(ServiceValidationError):
        google._prepare_vision_data(
            make_coverage_call(response_format="json", structure="{")
        )

    groq = Groq(coverage_hass, "k", "llama")
    with pytest.raises(ServiceValidationError):
        await groq._make_request({"choices": [{"message": "bad"}]})
    with pytest.raises(ServiceValidationError):
        await groq._make_request({"choices": [{"message": {}}]})
    assert "response_format" not in groq._prepare_vision_data(
        make_coverage_call(response_format="json", structure="{")
    )
    assert "response_format" not in groq._prepare_text_data(
        make_coverage_call(response_format="json", structure="{")
    )

    localai = LocalAI(
        coverage_hass,
        "",
        "llava",
        endpoint={"ip_address": "127.0.0.1", "port": "8080", "https": False},
    )
    with pytest.raises(ServiceValidationError):
        await localai._make_request({"choices": ["bad"]})
    with pytest.raises(ServiceValidationError):
        await localai._make_request({"choices": [{"message": "bad"}]})
    with pytest.raises(ServiceValidationError):
        await localai._make_request({"choices": [{"message": {}}]})
    with pytest.raises(ServiceValidationError):
        localai._prepare_vision_data(
            make_coverage_call(response_format="json", structure="{")
        )
    assert (
        localai._prepare_text_data(
            make_coverage_call(response_format="json", structure={"type": "object"})
        )["response_format"]["json_schema"]["name"]
        == "response"
    )
    bad_local = LocalAI(coverage_hass, "", "m", endpoint={"ip_address": "", "port": ""})
    with pytest.raises(ServiceValidationError):
        await bad_local.validate()

    ollama = Ollama(
        coverage_hass,
        "",
        "llava",
        endpoint={"ip_address": "127.0.0.1", "port": "11434", "https": False},
    )
    with pytest.raises(ServiceValidationError):
        await ollama._make_request("bad")
    with pytest.raises(ServiceValidationError):
        ollama._prepare_vision_data(
            make_coverage_call(response_format="json", structure="{")
        )
    assert (
        ollama._prepare_text_data(
            make_coverage_call(response_format="json", structure={"type": "object"})
        )["format"]["type"]
        == "object"
    )
    bad_ollama = Ollama(coverage_hass, "", "m", endpoint={"ip_address": "", "port": ""})
    with pytest.raises(ServiceValidationError):
        await bad_ollama.validate()

    aws = AWSBedrock(coverage_hass, "", "", "us-east-1", "m", api_key="k")
    with pytest.raises(ServiceValidationError):
        await aws._make_request("bad")
    with pytest.raises(ServiceValidationError):
        await aws._make_request({"output": {}})
    with pytest.raises(ServiceValidationError):
        await aws._make_request({"output": {"message": "bad"}})
    with pytest.raises(ServiceValidationError):
        await aws._make_request({"output": {"message": {"content": ["bad"]}}})

    iam = AWSBedrock(coverage_hass, "AK", "SK", "us-east-1", "m")
    iam.invoke_bedrock = AsyncMock(return_value="bad")
    with pytest.raises(ServiceValidationError):
        await iam._make_request({})
    iam.invoke_bedrock = AsyncMock(return_value={"message": "bad"})
    with pytest.raises(ServiceValidationError):
        await iam._make_request({})
    iam.invoke_bedrock = AsyncMock(return_value={"message": {"content": ["bad"]}})
    with pytest.raises(ServiceValidationError):
        await iam._make_request({})


@pytest.mark.anyio
async def test_aws_invoke_and_text_validate_paths(coverage_hass):
    provider = AWSBedrock(coverage_hass, "AK", "SK", "us-east-1", "m")
    client = Mock()
    client.converse = Mock(
        return_value={
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "metrics": {"latencyMs": 1},
            "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
            "output": {"message": {"content": [{"text": "ok"}]}},
        }
    )
    coverage_hass.async_add_executor_job = AsyncMock(
        side_effect=[client, client.converse()]
    )
    out = await provider.invoke_bedrock(
        "m",
        {
            "messages": [],
            "inferenceConfig": {},
            "toolConfig": {"t": 1},
            "system": [{"text": "s"}],
        },
    )
    assert "message" in out

    coverage_hass.async_add_executor_job = AsyncMock(side_effect=RuntimeError("x"))
    with pytest.raises(ServiceValidationError):
        await provider.invoke_bedrock("m", {"messages": [], "inferenceConfig": {}})

    assert (
        provider._prepare_text_data(
            make_coverage_call(response_format="json", structure={"type": "object"})
        )["toolConfig"]["tools"][0]["toolSpec"]["name"]
        == "return_structured_data"
    )
    with pytest.raises(ServiceValidationError):
        provider._prepare_vision_data(
            make_coverage_call(response_format="json", structure="{")
        )
    with pytest.raises(ServiceValidationError):
        provider._prepare_text_data(
            make_coverage_call(response_format="json", structure="{")
        )

    provider.invoke_bedrock = AsyncMock(return_value={"ok": True})
    await provider.validate()


@pytest.mark.anyio
async def test_all_providers_run_both_vision_and_text_requests(coverage_hass):
    def mk_call(**kwargs):
        return make_coverage_call(
            use_memory=True,
            response_format="json",
            structure={"type": "object"},
            **kwargs,
        )

    providers = [
        OpenAI(coverage_hass, "k", "gpt-4o"),
        AzureOpenAI(
            coverage_hass,
            "k",
            "gpt-4",
            endpoint={
                "base_url": "https://{base_url}/{deployment}?api-version={api_version}",
                "endpoint": "ep",
                "deployment": "dep",
                "api_version": "2025-01-01",
            },
        ),
        Anthropic(coverage_hass, "k", "claude"),
        Google(coverage_hass, "k", "gemini-2.5-pro"),
        Groq(coverage_hass, "k", "llama"),
        LocalAI(
            coverage_hass,
            "",
            "llava",
            endpoint={"ip_address": "127.0.0.1", "port": "8080", "https": False},
        ),
        Ollama(
            coverage_hass,
            "",
            "qwen3.5",
            endpoint={"ip_address": "127.0.0.1", "port": "11434", "https": False},
        ),
        AWSBedrock(coverage_hass, "", "", "us-east-1", "m", api_key="token"),
    ]

    for provider in providers:
        provider._make_request = AsyncMock(
            side_effect=lambda data: f"ok-{list(data.keys())[0]}"
        )
        assert (await provider.vision_request(mk_call())).startswith("ok-")
        assert (await provider.title_request(mk_call())).startswith("ok-")


def test_provider_factory_openrouter_branch(coverage_hass):
    cfg = {CONF_API_KEY: "k"}
    created = ProviderFactory.create(coverage_hass, "OpenRouter", cfg, "m")
    assert isinstance(created, OpenAI)


@pytest.mark.anyio
async def test_request_glimpse_outer_exception_and_resolve_error_tail(
    coverage_hass, monkeypatch
):
    req = Request(coverage_hass, "m", 10, 0.2)
    req.base64_images = ["aW1n"]
    req.filenames = ["f.jpg"]
    monkeypatch.setattr(
        ProviderFactory, "create", lambda **kwargs: DummyProvider(response_text="ok")
    )

    call_obj = make_coverage_call()
    call_obj.model_is_glimpse = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    result = await req.call(call_obj)
    assert result["response_text"] == "ok"

    # Trigger inner Glimpse parse exception path (json.loads receives non-string).
    monkeypatch.setattr(
        ProviderFactory,
        "create",
        lambda **kwargs: DummyProvider(response_text={"bad": True}),
    )
    parsed_fail_call = make_coverage_call(response_format="text")
    parsed_fail_call.model_is_glimpse = lambda: True
    result = await req.call(parsed_fail_call)
    assert isinstance(result["response_text"], dict)

    provider = MinimalProvider(coverage_hass, "", "m")
    response = Mock()
    response.text = AsyncMock(return_value='{"error":"boom"}')
    assert await provider._resolve_error(response, "openai") == "boom"

    response.text = AsyncMock(return_value="[]")
    assert await provider._resolve_error(response, "openai") == "Unknown error"


@pytest.mark.anyio
async def test_provider_remaining_error_branches(coverage_hass, monkeypatch):
    openai = OpenAI(coverage_hass, "k", "gpt-5-mini")
    payload = openai._prepare_text_data(make_coverage_call())
    assert "temperature" not in payload

    azure = AzureOpenAI(
        coverage_hass,
        "k",
        "gpt-4",
        endpoint={
            "base_url": "https://{base_url}/{deployment}?api-version={api_version}",
            "endpoint": "ep",
            "deployment": "dep",
            "api_version": "2025-01-01",
        },
    )
    azure._post = AsyncMock(return_value={"choices": []})
    with pytest.raises(ServiceValidationError):
        await azure._make_request({})
    azure._post = AsyncMock(return_value={"choices": ["bad"]})
    with pytest.raises(ServiceValidationError):
        await azure._make_request({})

    google = Google(coverage_hass, "k", "gemini-pro")
    google._post = AsyncMock(return_value={"candidates": [{"content": {}}]})
    with pytest.raises(ServiceValidationError):
        await google._make_request({})

    groq = Groq(coverage_hass, "k", "llama")
    groq._post = AsyncMock(return_value={"choices": ["bad"]})
    with pytest.raises(ServiceValidationError):
        await groq._make_request({})
    groq._post = AsyncMock(return_value={"choices": [{"message": "bad"}]})
    with pytest.raises(ServiceValidationError):
        await groq._make_request({})
    groq._post = AsyncMock(return_value={"choices": [{"message": {}}]})
    with pytest.raises(ServiceValidationError):
        await groq._make_request({})

    localai = LocalAI(
        coverage_hass,
        "",
        "llava",
        endpoint={"ip_address": "127.0.0.1", "port": "8080", "https": False},
    )
    localai._post = AsyncMock(return_value="bad")
    with pytest.raises(ServiceValidationError):
        await localai._make_request({})
    localai._post = AsyncMock(return_value={"choices": ["bad"]})
    with pytest.raises(ServiceValidationError):
        await localai._make_request({})
    localai._post = AsyncMock(return_value={"choices": [{"message": "bad"}]})
    with pytest.raises(ServiceValidationError):
        await localai._make_request({})
    localai._post = AsyncMock(return_value={"choices": [{"message": {}}]})
    with pytest.raises(ServiceValidationError):
        await localai._make_request({})

    ollama = Ollama(
        coverage_hass,
        "",
        "llava",
        endpoint={"ip_address": "127.0.0.1", "port": "11434", "https": False},
    )
    ollama._post = AsyncMock(return_value="bad")
    with pytest.raises(ServiceValidationError):
        await ollama._make_request({})

    session = Mock()
    session.get = AsyncMock(return_value=SimpleNamespace(status=500))
    monkeypatch.setattr(
        "custom_components.llmvision.providers.async_get_clientsession",
        lambda hass: session,
    )
    with pytest.raises(ServiceValidationError):
        await ollama.validate()

    bearer = AWSBedrock(
        coverage_hass,
        aws_access_key_id="",
        aws_secret_access_key="",
        aws_region_name="us-east-1",
        model="m",
        api_key="token",
    )
    bearer._post = AsyncMock(return_value="bad")
    with pytest.raises(ServiceValidationError):
        await bearer._make_request({})
    bearer._post = AsyncMock(return_value={"output": "bad"})
    with pytest.raises(ServiceValidationError):
        await bearer._make_request({})
    bearer._post = AsyncMock(return_value={"output": {"message": "bad"}})
    with pytest.raises(ServiceValidationError):
        await bearer._make_request({})
    bearer._post = AsyncMock(return_value={"output": {"message": {"content": ["bad"]}}})
    with pytest.raises(ServiceValidationError):
        await bearer._make_request({})

    iam = AWSBedrock(coverage_hass, "AK", "SK", "us-east-1", "m")
    iam.invoke_bedrock = AsyncMock(return_value={"message": {"content": []}})
    assert await iam._make_request({}) == ""
    iam.invoke_bedrock = AsyncMock(
        return_value={"message": {"content": [{"toolUse": {"input": {"x": 1}}}]}}
    )
    assert await iam._make_request({}) == '{"x": 1}'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
