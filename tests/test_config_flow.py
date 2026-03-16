"""Unit tests for config_flow.py module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant import config_entries
from homeassistant.exceptions import ServiceValidationError

from custom_components.llmvision.config_flow import flatten_dict, llmvisionConfigFlow
from custom_components.llmvision.const import (
    CONF_API_KEY,
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_REGION_NAME,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_AZURE_BASE_URL,
    CONF_AZURE_DEPLOYMENT,
    CONF_AZURE_VERSION,
    CONF_CONTEXT_WINDOW,
    CONF_CUSTOM_OPENAI_ENDPOINT,
    CONF_DEFAULT_MODEL,
    CONF_FALLBACK_PROVIDER,
    CONF_HTTPS,
    CONF_IP_ADDRESS,
    CONF_KEEP_ALIVE,
    CONF_MEMORY_PATHS,
    CONF_MEMORY_STRINGS,
    CONF_PORT,
    CONF_PROVIDER,
    CONF_REASONING_EFFORT,
    CONF_REQUEST_TIMEOUT,
    CONF_RETENTION_TIME,
    CONF_SYSTEM_PROMPT,
    CONF_TEMPERATURE,
    CONF_THINK,
    CONF_THINKING_BUDGET,
    CONF_TIMELINE_LANGUAGE,
    CONF_TITLE_PROMPT,
    CONF_TOP_P,
    DEFAULT_OPENAI_MODEL,
    ENDPOINT_AZURE,
    ENDPOINT_OPENROUTER,
    ENDPOINT_OPENWEBUI,
    VERSION_AZURE,
)


@pytest.fixture
def build_flow(mock_hass):
    """Create a config flow with patched Home Assistant helpers."""

    def _build(source=config_entries.SOURCE_USER, init_info=None):
        flow = llmvisionConfigFlow()
        flow.hass = mock_hass
        flow.context = {"source": source}
        if init_info is not None:
            flow.init_info = init_info

        flow.async_show_form = Mock(
            side_effect=lambda **kwargs: {"type": "form", **kwargs}
        )
        flow.async_create_entry = Mock(
            side_effect=lambda title, data: {
                "type": "create_entry",
                "title": title,
                "data": data,
            }
        )
        flow.async_abort = Mock(
            side_effect=lambda **kwargs: {"type": "abort", **kwargs}
        )
        flow.async_update_reload_and_abort = Mock(
            side_effect=lambda entry, data_updates: {
                "type": "update",
                "entry": entry,
                "data_updates": data_updates,
            }
        )
        flow.add_suggested_values_to_schema = Mock(side_effect=lambda schema, _: schema)
        return flow

    return _build


class TestConfigFlow:
    """Test llmvisionConfigFlow class."""

    def test_init(self):
        """Test llmvisionConfigFlow initialization."""
        flow = llmvisionConfigFlow()

        assert flow.VERSION == 4
        assert flow.MINOR_VERSION == 0

    @pytest.mark.asyncio
    async def test_handle_provider_dispatches_known_provider(self, build_flow):
        """Known provider names should call the matching step method."""
        flow = build_flow()
        flow.async_step_openai = AsyncMock(return_value={"type": "openai"})

        result = await flow.handle_provider("OpenAI")

        assert result == {"type": "openai"}
        flow.async_step_openai.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_handle_provider_aborts_unknown_provider(self, build_flow):
        """Unknown providers should abort cleanly."""
        flow = build_flow()

        result = await flow.handle_provider("Invalid Provider")

        assert result == {"type": "abort", "reason": "unknown_provider"}
        flow.async_abort.assert_called_once_with(reason="unknown_provider")

    @pytest.mark.asyncio
    async def test_async_step_user_redirects_to_settings_when_missing(
        self, build_flow, mock_hass
    ):
        """First-time setup should force the settings flow."""
        flow = build_flow()
        mock_hass.config_entries.async_entries.return_value = [
            Mock(data={CONF_PROVIDER: "OpenAI"})
        ]
        flow.async_step_settings = AsyncMock(return_value={"type": "settings"})

        result = await flow.async_step_user()

        assert result == {"type": "settings"}
        assert flow.init_info == {CONF_PROVIDER: "Settings"}
        flow.async_step_settings.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_async_step_user_dispatches_selected_provider(
        self, build_flow, mock_hass
    ):
        """Provider selection should hand off to the provider-specific step."""
        flow = build_flow()
        mock_hass.config_entries.async_entries.return_value = [
            Mock(data={CONF_PROVIDER: "Settings"})
        ]
        flow.handle_provider = AsyncMock(return_value={"type": "provider"})

        result = await flow.async_step_user({CONF_PROVIDER: "OpenAI"})

        assert result == {"type": "provider"}
        assert flow.init_info == {CONF_PROVIDER: "OpenAI"}
        flow.handle_provider.assert_awaited_once_with("OpenAI")

    @pytest.mark.asyncio
    async def test_async_step_user_shows_provider_form_when_settings_exist(
        self, build_flow, mock_hass
    ):
        """Once settings exist, the user step should render the provider chooser."""
        flow = build_flow()
        mock_hass.config_entries.async_entries.return_value = [
            Mock(data={CONF_PROVIDER: "Settings"})
        ]

        result = await flow.async_step_user()

        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_async_step_reconfigure_uses_existing_provider(self, build_flow):
        """Reconfigure should dispatch using the current entry provider."""
        flow = build_flow(source=config_entries.SOURCE_RECONFIGURE)
        entry = Mock(data={CONF_PROVIDER: "Azure"})
        flow._get_reconfigure_entry = Mock(return_value=entry)
        flow.handle_provider = AsyncMock(return_value={"type": "azure"})

        result = await flow.async_step_reconfigure({})

        assert result == {"type": "azure"}
        assert flow.init_info == entry.data
        flow.handle_provider.assert_awaited_once_with("Azure")


class TestSettingsStep:
    """Test settings step behavior and validation."""

    @pytest.mark.asyncio
    async def test_settings_creates_entry_and_defaults_missing_memory_fields(
        self, build_flow
    ):
        """Missing memory fields should be normalized to empty lists."""
        flow = build_flow(init_info={CONF_PROVIDER: "Settings"})
        user_input = {
            "general_section": {
                CONF_FALLBACK_PROVIDER: "no_fallback",
                CONF_REQUEST_TIMEOUT: 60,
            },
            "prompt_section": {
                CONF_SYSTEM_PROMPT: "system",
                CONF_TITLE_PROMPT: "title",
            },
            "timeline_section": {
                CONF_TIMELINE_LANGUAGE: "English",
                CONF_RETENTION_TIME: 7,
            },
        }

        result = await flow.async_step_settings(user_input)

        assert result["type"] == "create_entry"
        assert result["title"] == "LLM Vision Settings"
        assert result["data"][CONF_PROVIDER] == "Settings"
        assert result["data"][CONF_MEMORY_PATHS] == []
        assert result["data"][CONF_MEMORY_STRINGS] == []

    @pytest.mark.asyncio
    async def test_settings_rejects_mismatched_memory_lengths(self, build_flow):
        """Configured memory paths and strings must have matching lengths."""
        flow = build_flow(init_info={CONF_PROVIDER: "Settings"})
        user_input = {
            "general_section": {
                CONF_FALLBACK_PROVIDER: "no_fallback",
                CONF_REQUEST_TIMEOUT: 60,
            },
            "prompt_section": {
                CONF_SYSTEM_PROMPT: "system",
                CONF_TITLE_PROMPT: "title",
            },
            "timeline_section": {
                CONF_TIMELINE_LANGUAGE: "English",
                CONF_RETENTION_TIME: 7,
            },
            "memory_section": {
                CONF_MEMORY_PATHS: ["/tmp/image.jpg"],
                CONF_MEMORY_STRINGS: [],
            },
        }

        with patch(
            "custom_components.llmvision.config_flow.os.path.exists", return_value=True
        ):
            result = await flow.async_step_settings(user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "settings"
        assert result["errors"] == {"base": "mismatched_lengths"}

    @pytest.mark.asyncio
    async def test_settings_rejects_invalid_memory_path(self, build_flow):
        """Configured memory image paths must exist."""
        flow = build_flow(init_info={CONF_PROVIDER: "Settings"})
        user_input = {
            "general_section": {
                CONF_FALLBACK_PROVIDER: "no_fallback",
                CONF_REQUEST_TIMEOUT: 60,
            },
            "prompt_section": {
                CONF_SYSTEM_PROMPT: "system",
                CONF_TITLE_PROMPT: "title",
            },
            "timeline_section": {
                CONF_TIMELINE_LANGUAGE: "English",
                CONF_RETENTION_TIME: 7,
            },
            "memory_section": {
                CONF_MEMORY_PATHS: ["/missing/image.jpg"],
                CONF_MEMORY_STRINGS: ["Front door"],
            },
        }

        with patch(
            "custom_components.llmvision.config_flow.os.path.exists", return_value=False
        ):
            result = await flow.async_step_settings(user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "settings"
        assert result["errors"] == {"base": "invalid_image_path"}

    @pytest.mark.asyncio
    async def test_settings_reconfigure_updates_existing_entry(self, build_flow):
        """Reconfiguring settings should update the current entry."""
        existing_entry = Mock(
            data={
                CONF_PROVIDER: "Settings",
                CONF_FALLBACK_PROVIDER: "no_fallback",
                CONF_REQUEST_TIMEOUT: 60,
            }
        )
        flow = build_flow(source=config_entries.SOURCE_RECONFIGURE)
        flow._get_reconfigure_entry = Mock(return_value=existing_entry)
        user_input = {
            "general_section": {
                CONF_FALLBACK_PROVIDER: "provider-entry-id",
                CONF_REQUEST_TIMEOUT: 120,
            },
            "prompt_section": {
                CONF_SYSTEM_PROMPT: "system",
                CONF_TITLE_PROMPT: "title",
            },
            "timeline_section": {
                CONF_TIMELINE_LANGUAGE: "English",
                CONF_RETENTION_TIME: 14,
            },
            "memory_section": {
                CONF_MEMORY_PATHS: [],
                CONF_MEMORY_STRINGS: [],
            },
        }

        result = await flow.async_step_settings(user_input)

        assert result["type"] == "update"
        assert result["entry"] is existing_entry
        assert result["data_updates"][CONF_PROVIDER] == "Settings"
        assert result["data_updates"][CONF_FALLBACK_PROVIDER] == "provider-entry-id"
        assert result["data_updates"][CONF_REQUEST_TIMEOUT] == 120

    @pytest.mark.asyncio
    async def test_settings_shows_form_without_input(self, build_flow, mock_hass):
        """The settings step should render a form when opened without input."""
        flow = build_flow(init_info={CONF_PROVIDER: "Settings"})
        mock_hass.data = {
            "llmvision": {
                "settings-entry": {CONF_PROVIDER: "Settings"},
                "openai-entry": {CONF_PROVIDER: "OpenAI"},
            }
        }

        result = await flow.async_step_settings()

        assert result["type"] == "form"
        assert result["step_id"] == "settings"


class TestProviderSteps:
    """Test representative provider-specific flow paths."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("step_name", "init_provider"),
        [
            ("openai", "OpenAI"),
            ("azure", "Azure"),
            ("anthropic", "Anthropic"),
            ("google", "Google"),
            ("groq", "Groq"),
            ("custom_openai", "Custom OpenAI"),
            ("aws_bedrock", "AWS Bedrock"),
            ("localai", "LocalAI"),
            ("ollama", "Ollama"),
            ("openwebui", "OpenWebUI"),
            ("openrouter", "OpenRouter"),
        ],
    )
    async def test_provider_steps_show_form_without_input(
        self, build_flow, step_name, init_provider
    ):
        """Every provider step should render its form when opened without input."""
        flow = build_flow(init_info={CONF_PROVIDER: init_provider})

        result = await getattr(flow, f"async_step_{step_name}")()

        assert result["type"] == "form"
        assert result["step_id"] == step_name

    @pytest.mark.asyncio
    async def test_openai_creates_entry_after_successful_validation(self, build_flow):
        """OpenAI setup should validate and create a config entry."""
        flow = build_flow(init_info={CONF_PROVIDER: "OpenAI"})
        user_input = {
            "connection_section": {CONF_API_KEY: "secret"},
            "model_section": {
                CONF_DEFAULT_MODEL: DEFAULT_OPENAI_MODEL,
                CONF_TEMPERATURE: 0.4,
                CONF_TOP_P: 0.8,
                CONF_REASONING_EFFORT: "medium",
            },
        }
        provider_instance = Mock(validate=AsyncMock())

        with patch(
            "custom_components.llmvision.config_flow.OpenAI",
            return_value=provider_instance,
        ) as openai_cls:
            result = await flow.async_step_openai(user_input)

        assert result["type"] == "create_entry"
        assert result["title"] == "OpenAI"
        assert result["data"][CONF_PROVIDER] == "OpenAI"
        openai_cls.assert_called_once_with(
            flow.hass,
            api_key="secret",
            model=DEFAULT_OPENAI_MODEL,
        )
        provider_instance.validate.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_openai_shows_error_when_validation_fails(self, build_flow):
        """Validation failures should return the handshake form error."""
        flow = build_flow(init_info={CONF_PROVIDER: "OpenAI"})
        user_input = {
            "connection_section": {CONF_API_KEY: "secret"},
            "model_section": {
                CONF_DEFAULT_MODEL: DEFAULT_OPENAI_MODEL,
                CONF_TEMPERATURE: 0.5,
                CONF_TOP_P: 0.9,
                CONF_REASONING_EFFORT: "none",
            },
        }
        provider_instance = Mock(
            validate=AsyncMock(side_effect=ServiceValidationError("boom"))
        )

        with patch(
            "custom_components.llmvision.config_flow.OpenAI",
            return_value=provider_instance,
        ):
            result = await flow.async_step_openai(user_input)

        assert result["type"] == "form"
        assert result["step_id"] == "openai"
        assert result["errors"] == {"base": "handshake_failed"}

    @pytest.mark.asyncio
    async def test_azure_reconfigure_updates_entry_after_validation(self, build_flow):
        """Azure reconfigure should validate and update the existing entry."""
        existing_entry = Mock(
            data={
                CONF_PROVIDER: "Azure",
                CONF_API_KEY: "old-secret",
                CONF_AZURE_BASE_URL: "https://old.openai.azure.com/",
                CONF_AZURE_DEPLOYMENT: "old-deployment",
                CONF_AZURE_VERSION: VERSION_AZURE,
                CONF_DEFAULT_MODEL: "gpt-4o-mini",
            }
        )
        flow = build_flow(source=config_entries.SOURCE_RECONFIGURE)
        flow._get_reconfigure_entry = Mock(return_value=existing_entry)
        user_input = {
            "connection_section": {
                CONF_API_KEY: "secret",
                CONF_AZURE_BASE_URL: "https://domain.openai.azure.com/",
                CONF_AZURE_DEPLOYMENT: "deployment",
                CONF_AZURE_VERSION: VERSION_AZURE,
            },
            "model_section": {
                CONF_DEFAULT_MODEL: "gpt-4o-mini",
                CONF_TEMPERATURE: 0.3,
                CONF_TOP_P: 0.7,
            },
        }
        provider_instance = Mock(validate=AsyncMock())

        with patch(
            "custom_components.llmvision.config_flow.AzureOpenAI",
            return_value=provider_instance,
        ) as azure_cls:
            result = await flow.async_step_azure(user_input)

        assert result["type"] == "update"
        assert result["entry"] is existing_entry
        assert result["data_updates"][CONF_PROVIDER] == "Azure"
        azure_cls.assert_called_once_with(
            flow.hass,
            api_key="secret",
            model="gpt-4o-mini",
            endpoint={
                "base_url": ENDPOINT_AZURE,
                "endpoint": "https://domain.openai.azure.com/",
                "deployment": "deployment",
                "api_version": VERSION_AZURE,
            },
        )
        provider_instance.validate.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_ollama_strips_protocol_before_validation(self, build_flow):
        """Ollama host values should have any protocol prefix removed."""
        flow = build_flow(init_info={CONF_PROVIDER: "Ollama"})
        user_input = {
            "connection_section": {
                CONF_IP_ADDRESS: "https://ollama.local",
                CONF_PORT: 11434,
                CONF_HTTPS: True,
            },
            "model_section": {
                CONF_DEFAULT_MODEL: "gemma3:4b",
                CONF_TEMPERATURE: 0.5,
                CONF_TOP_P: 0.9,
                CONF_THINK: False,
            },
            "advanced_section": {
                CONF_CONTEXT_WINDOW: 4096,
                CONF_KEEP_ALIVE: "10m",
            },
        }
        provider_instance = Mock(validate=AsyncMock())

        with patch(
            "custom_components.llmvision.config_flow.Ollama",
            return_value=provider_instance,
        ) as ollama_cls:
            result = await flow.async_step_ollama(user_input)

        assert result["type"] == "create_entry"
        assert result["title"] == "Ollama (https://ollama.local)"
        ollama_cls.assert_called_once_with(
            flow.hass,
            api_key="",
            model="gemma3:4b",
            endpoint={
                "ip_address": "ollama.local",
                "port": 11434,
                "https": True,
                "keep_alive": "10m",
                "context_window": 4096,
            },
        )
        provider_instance.validate.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_localai_reconfigure_updates_existing_entry(self, build_flow):
        """LocalAI reconfigure should update the existing entry after validation."""
        existing_entry = Mock(
            data={
                CONF_PROVIDER: "LocalAI",
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_PORT: 8080,
                CONF_HTTPS: False,
                CONF_DEFAULT_MODEL: "llava",
            }
        )
        flow = build_flow(source=config_entries.SOURCE_RECONFIGURE)
        flow._get_reconfigure_entry = Mock(return_value=existing_entry)
        user_input = {
            "connection_section": {
                CONF_IP_ADDRESS: "localhost",
                CONF_PORT: 8081,
                CONF_HTTPS: True,
            },
            "model_section": {
                CONF_DEFAULT_MODEL: "llava",
                CONF_TEMPERATURE: 0.6,
                CONF_TOP_P: 0.95,
            },
        }
        provider_instance = Mock(validate=AsyncMock())

        with patch(
            "custom_components.llmvision.config_flow.LocalAI",
            return_value=provider_instance,
        ) as localai_cls:
            result = await flow.async_step_localai(user_input)

        assert result["type"] == "update"
        assert result["entry"] is existing_entry
        localai_cls.assert_called_once_with(
            flow.hass,
            api_key="",
            model="llava",
            endpoint={
                "ip_address": "localhost",
                "port": 8081,
                "https": True,
            },
        )
        provider_instance.validate.assert_awaited_once_with()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "step_name",
            "init_provider",
            "patch_target",
            "user_input",
            "expected_title",
            "expected_call",
            "expected_error",
        ),
        [
            (
                "anthropic",
                "Anthropic",
                "custom_components.llmvision.config_flow.Anthropic",
                {
                    "connection_section": {CONF_API_KEY: "secret"},
                    "model_section": {
                        CONF_DEFAULT_MODEL: "claude-3-7-sonnet-latest",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                        CONF_THINKING_BUDGET: 1024,
                    },
                },
                "Anthropic Claude",
                lambda flow: (
                    (flow.hass,),
                    {"api_key": "secret", "model": "claude-3-7-sonnet-latest"},
                ),
                "empty_api_key",
            ),
            (
                "google",
                "Google",
                "custom_components.llmvision.config_flow.Google",
                {
                    "connection_section": {CONF_API_KEY: "secret"},
                    "model_section": {
                        CONF_DEFAULT_MODEL: "gemini-2.0-flash",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                        CONF_THINKING_BUDGET: 100,
                    },
                },
                "Google Gemini",
                lambda flow: (
                    (flow.hass,),
                    {"api_key": "secret", "model": "gemini-2.0-flash"},
                ),
                "empty_api_key",
            ),
            (
                "groq",
                "Groq",
                "custom_components.llmvision.config_flow.Groq",
                {
                    "connection_section": {CONF_API_KEY: "secret"},
                    "model_section": {
                        CONF_DEFAULT_MODEL: "llama",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                    },
                },
                "Groq",
                lambda flow: (
                    (flow.hass,),
                    {"api_key": "secret", "model": "llama"},
                ),
                "handshake_failed",
            ),
            (
                "custom_openai",
                "Custom OpenAI",
                "custom_components.llmvision.config_flow.OpenAI",
                {
                    "connection_section": {
                        CONF_API_KEY: "secret",
                        CONF_CUSTOM_OPENAI_ENDPOINT: "http://host.example/v1/chat/completions",
                    },
                    "model_section": {
                        CONF_DEFAULT_MODEL: "custom-model",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                    },
                },
                "Custom OpenAI compatible Provider",
                lambda flow: (
                    (flow.hass,),
                    {
                        "api_key": "secret",
                        "model": "custom-model",
                        "endpoint": {
                            "base_url": "http://host.example/v1/chat/completions"
                        },
                    },
                ),
                "handshake_failed",
            ),
            (
                "aws_bedrock",
                "AWS Bedrock",
                "custom_components.llmvision.config_flow.AWSBedrock",
                {
                    "connection_section": {
                        CONF_AWS_ACCESS_KEY_ID: "key-id",
                        CONF_AWS_SECRET_ACCESS_KEY: "secret-key",
                        CONF_AWS_REGION_NAME: "us-east-1",
                    },
                    "model_section": {
                        CONF_DEFAULT_MODEL: "nova-pro",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                    },
                },
                "AWS Bedrock Provider",
                lambda flow: (
                    (),
                    {
                        "hass": flow.hass,
                        "aws_access_key_id": "key-id",
                        "aws_secret_access_key": "secret-key",
                        "aws_region_name": "us-east-1",
                        "model": "nova-pro",
                    },
                ),
                "handshake_failed",
            ),
            (
                "openwebui",
                "OpenWebUI",
                "custom_components.llmvision.config_flow.OpenAI",
                {
                    "connection_section": {
                        CONF_API_KEY: "secret",
                        CONF_IP_ADDRESS: "https://openwebui.local",
                        CONF_PORT: 3000,
                        CONF_HTTPS: True,
                    },
                    "model_section": {
                        CONF_DEFAULT_MODEL: "gemma3:4b",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                    },
                },
                "OpenWebUI (https://openwebui.local)",
                lambda flow: (
                    (),
                    {
                        "hass": flow.hass,
                        "api_key": "secret",
                        "model": "gemma3:4b",
                        "endpoint": {
                            "base_url": ENDPOINT_OPENWEBUI.format(
                                ip_address="openwebui.local",
                                port=3000,
                                protocol="https",
                            )
                        },
                    },
                ),
                "handshake_failed",
            ),
            (
                "openrouter",
                "OpenRouter",
                "custom_components.llmvision.config_flow.OpenAI",
                {
                    "connection_section": {CONF_API_KEY: "secret"},
                    "model_section": {
                        CONF_DEFAULT_MODEL: "google/gemma-3-4b-it:free",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                        CONF_REASONING_EFFORT: "low",
                    },
                },
                "OpenRouter",
                lambda flow: (
                    (flow.hass,),
                    {
                        "api_key": "secret",
                        "model": "google/gemma-3-4b-it:free",
                        "endpoint": {"base_url": ENDPOINT_OPENROUTER},
                    },
                ),
                "handshake_failed",
            ),
        ],
    )
    async def test_provider_steps_create_entries_after_successful_validation(
        self,
        build_flow,
        step_name,
        init_provider,
        patch_target,
        user_input,
        expected_title,
        expected_call,
        expected_error,
    ):
        """Repeated provider steps should validate and create entries correctly."""
        flow = build_flow(init_info={CONF_PROVIDER: init_provider})
        provider_instance = Mock(validate=AsyncMock())

        with patch(patch_target, return_value=provider_instance) as provider_cls:
            result = await getattr(flow, f"async_step_{step_name}")(user_input)

        expected_args, expected_kwargs = expected_call(flow)
        assert result["type"] == "create_entry"
        assert result["title"] == expected_title
        assert result["data"][CONF_PROVIDER] == init_provider
        provider_cls.assert_called_once_with(*expected_args, **expected_kwargs)
        provider_instance.validate.assert_awaited_once_with()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("step_name", "init_provider", "patch_target", "user_input", "expected_error"),
        [
            (
                "anthropic",
                "Anthropic",
                "custom_components.llmvision.config_flow.Anthropic",
                {
                    "connection_section": {CONF_API_KEY: "secret"},
                    "model_section": {
                        CONF_DEFAULT_MODEL: "claude-3-7-sonnet-latest",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                        CONF_THINKING_BUDGET: 0,
                    },
                },
                "empty_api_key",
            ),
            (
                "google",
                "Google",
                "custom_components.llmvision.config_flow.Google",
                {
                    "connection_section": {CONF_API_KEY: "secret"},
                    "model_section": {
                        CONF_DEFAULT_MODEL: "gemini-2.0-flash",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                        CONF_THINKING_BUDGET: 0,
                    },
                },
                "empty_api_key",
            ),
            (
                "groq",
                "Groq",
                "custom_components.llmvision.config_flow.Groq",
                {
                    "connection_section": {CONF_API_KEY: "secret"},
                    "model_section": {
                        CONF_DEFAULT_MODEL: "llama",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                    },
                },
                "handshake_failed",
            ),
            (
                "custom_openai",
                "Custom OpenAI",
                "custom_components.llmvision.config_flow.OpenAI",
                {
                    "connection_section": {
                        CONF_API_KEY: "secret",
                        CONF_CUSTOM_OPENAI_ENDPOINT: "http://host.example/v1/chat/completions",
                    },
                    "model_section": {
                        CONF_DEFAULT_MODEL: "custom-model",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                    },
                },
                "handshake_failed",
            ),
            (
                "aws_bedrock",
                "AWS Bedrock",
                "custom_components.llmvision.config_flow.AWSBedrock",
                {
                    "connection_section": {
                        CONF_AWS_ACCESS_KEY_ID: "key-id",
                        CONF_AWS_SECRET_ACCESS_KEY: "secret-key",
                        CONF_AWS_REGION_NAME: "us-east-1",
                    },
                    "model_section": {
                        CONF_DEFAULT_MODEL: "nova-pro",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                    },
                },
                "handshake_failed",
            ),
            (
                "openwebui",
                "OpenWebUI",
                "custom_components.llmvision.config_flow.OpenAI",
                {
                    "connection_section": {
                        CONF_API_KEY: "secret",
                        CONF_IP_ADDRESS: "https://openwebui.local",
                        CONF_PORT: 3000,
                        CONF_HTTPS: True,
                    },
                    "model_section": {
                        CONF_DEFAULT_MODEL: "gemma3:4b",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                    },
                },
                "handshake_failed",
            ),
            (
                "openrouter",
                "OpenRouter",
                "custom_components.llmvision.config_flow.OpenAI",
                {
                    "connection_section": {CONF_API_KEY: "secret"},
                    "model_section": {
                        CONF_DEFAULT_MODEL: "google/gemma-3-4b-it:free",
                        CONF_TEMPERATURE: 0.5,
                        CONF_TOP_P: 0.9,
                        CONF_REASONING_EFFORT: "none",
                    },
                },
                "handshake_failed",
            ),
        ],
    )
    async def test_provider_steps_show_expected_errors_on_validation_failure(
        self,
        build_flow,
        step_name,
        init_provider,
        patch_target,
        user_input,
        expected_error,
    ):
        """Repeated provider steps should surface their configured validation errors."""
        flow = build_flow(init_info={CONF_PROVIDER: init_provider})
        provider_instance = Mock(
            validate=AsyncMock(side_effect=ServiceValidationError("boom"))
        )

        with patch(patch_target, return_value=provider_instance):
            result = await getattr(flow, f"async_step_{step_name}")(user_input)

        assert result["type"] == "form"
        assert result["step_id"] == step_name
        assert result["errors"] == {"base": expected_error}


class TestFlattenDict:
    """Test flatten_dict function."""

    def test_flatten_dict_simple(self):
        """Test flatten_dict with simple nested dict."""
        nested = {"section1": {"key1": "value1", "key2": "value2"}}

        result = flatten_dict(nested)

        assert result == {"key1": "value1", "key2": "value2"}

    def test_flatten_dict_multiple_sections(self):
        """Test flatten_dict with multiple sections."""
        nested = {
            "section1": {"key1": "value1"},
            "section2": {"key2": "value2"},
        }

        result = flatten_dict(nested)

        assert result == {"key1": "value1", "key2": "value2"}

    def test_flatten_dict_empty(self):
        """Test flatten_dict with empty dict."""
        result = flatten_dict({})

        assert result == {}

    def test_flatten_dict_no_nesting(self):
        """Test flatten_dict with flat dict."""
        flat = {"key1": "value1", "key2": "value2"}

        result = flatten_dict(flat)

        assert result == flat
