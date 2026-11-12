from abc import ABC, abstractmethod
from aiohttp import ClientTimeout
import boto3
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant
from functools import partial
from typing import Any, cast
import logging
import re
import json
import base64
from .models import SAMPLING_PARAMS, UNKNOWN, get, normalize_effort
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_PROVIDER,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_HTTPS,
    CONF_DEFAULT_MODEL,
    CONF_AZURE_BASE_URL,
    CONF_AZURE_DEPLOYMENT,
    CONF_AZURE_VERSION,
    CONF_ANTHROPIC_BASE_URL,
    CONF_CUSTOM_OPENAI_ENDPOINT,
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_AWS_REGION_NAME,
    VERSION_ANTHROPIC,
    ENDPOINT_OPENAI,
    ENDPOINT_AZURE,
    ENDPOINT_ANTHROPIC,
    ENDPOINT_GOOGLE,
    ENDPOINT_LOCALAI,
    ENDPOINT_OLLAMA,
    ENDPOINT_OPENWEBUI,
    ENDPOINT_GROQ,
    ENDPOINT_OPENROUTER,
    ENDPOINT_MISTRAL,
    ERROR_NOT_CONFIGURED,
    ERROR_GROQ_MULTIPLE_IMAGES,
    ERROR_NO_IMAGE_INPUT,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_AZURE_MODEL,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_LOCALAI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_CUSTOM_OPENAI_MODEL,
    DEFAULT_AWS_MODEL,
    DEFAULT_OPENWEBUI_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_MISTRAL_MODEL,
    CONF_KEEP_ALIVE,
    CONF_CONTEXT_WINDOW,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_THINKING_BUDGET,
    CONF_THINK,
    CONF_REASONING_EFFORT,
    CONF_REQUEST_TIMEOUT,
    CONF_SYSTEM_PROMPT,
    CONF_TITLE_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TITLE_PROMPT,
    GLIMPSE_V1_INSTRUCTIONS,
)

_LOGGER = logging.getLogger(__name__)


class _CompletionResponseError(ServiceValidationError):
    """A locally generated error safe to show without exposing provider content."""

    def __init__(self, *, token_limit: bool = False):
        message = (
            "The completion reached the token limit. Increase max_tokens "
            "or reduce reasoning effort if enabled; the limit may include "
            "reasoning and non-visible formatting tokens."
            if token_limit
            else "The provider returned no text (empty_response)."
        )
        super().__init__(message)


def _log_provider_failure(prefix: str, error: Exception) -> None:
    """Log a provider failure without exposing provider content.

    Errors raised by this module are safe to show; anything else may embed
    URLs, headers or payloads, so only its type is recorded.
    """
    if isinstance(error, ServiceValidationError):
        _LOGGER.error("%s (%s): %s", prefix, type(error).__name__, error)
    else:
        _LOGGER.error("%s (%s)", prefix, type(error).__name__)


class Request:

    def __init__(self, hass: HomeAssistant, message, max_tokens, temperature):
        self.session = async_get_clientsession(hass)
        self.hass = hass
        self.message = message
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.base64_images = []
        self.filenames = []

    @staticmethod
    def sanitize_data(data):
        """Remove long string data from request data to reduce log size"""
        if isinstance(data, dict):
            return {key: Request.sanitize_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [Request.sanitize_data(item) for item in data]
        elif isinstance(data, str) and len(data) > 400 and data.count(" ") < 50:
            return "<long_string>"
        elif isinstance(data, bytes) and len(data) > 400:
            return "<long_bytes>"
        else:
            return data

    @staticmethod
    def get_provider(hass, provider_uid):
        """Translate UID of the config entry into provider name"""
        if DOMAIN not in hass.data:
            return None

        entry_data = hass.data[DOMAIN].get(provider_uid)
        if not entry_data:
            return None

        return entry_data.get(CONF_PROVIDER)

    def get_default_model(self, provider):
        """Get default model from config entry"""
        domain_data = self.hass.data.get(DOMAIN) or {}
        config_entry = domain_data.get(provider)
        provider_name: str | None = self.get_provider(self.hass, provider)
        if provider_name is None:
            return None
        if config_entry:
            default_model = config_entry.get(CONF_DEFAULT_MODEL)
            if default_model:
                return default_model

        return {
            "OpenAI": DEFAULT_OPENAI_MODEL,
            "Azure": DEFAULT_AZURE_MODEL,
            "Anthropic": DEFAULT_ANTHROPIC_MODEL,
            "Google": DEFAULT_GOOGLE_MODEL,
            "Groq": DEFAULT_GROQ_MODEL,
            "LocalAI": DEFAULT_LOCALAI_MODEL,
            "Ollama": DEFAULT_OLLAMA_MODEL,
            "Custom OpenAI": DEFAULT_CUSTOM_OPENAI_MODEL,
            "AWS Bedrock": DEFAULT_AWS_MODEL,
            "AWS": DEFAULT_AWS_MODEL,  # For backwards compatibility
            "Open WebUI": DEFAULT_OPENWEBUI_MODEL,
            "OpenRouter": DEFAULT_OPENROUTER_MODEL,
            "Mistral": DEFAULT_MISTRAL_MODEL,
        }.get(provider_name)

    def validate(self, call: Any) -> None | ServiceValidationError:
        """Validate call data"""

        # if not call.model set default model for provider
        if not call.model:
            call.model = self.get_default_model(call.provider)
        # Check image input
        if not call.base64_images:
            raise ServiceValidationError(ERROR_NO_IMAGE_INPUT)
        # Check if single image is provided for Groq
        if (
            len(call.base64_images) > 1
            and self.get_provider(self.hass, call.provider) == "Groq"
        ):
            raise ServiceValidationError(ERROR_GROQ_MULTIPLE_IMAGES)
        # Check provider is configured
        if not call.provider:
            raise ServiceValidationError(ERROR_NOT_CONFIGURED)

    async def call(self, call: Any, _is_fallback_retry: bool = False):
        """
        Forwards a request to the specified provider and optionally generates a title.
        """
        entry_id = call.provider
        domain_data = self.hass.data.get(DOMAIN) or {}
        config = domain_data.get(entry_id)
        if config is None:
            raise ServiceValidationError(
                f"Provider config not found for entry_id: {entry_id}"
            )

        provider_name = Request.get_provider(self.hass, entry_id)
        if provider_name is None:
            raise ServiceValidationError("invalid_provider")
        # Ensure model defaults are respected
        call.model = getattr(call, "model", None) or self.get_default_model(entry_id)
        call.temperature = config.get(CONF_TEMPERATURE, 0.5)
        call.top_p = config.get(CONF_TOP_P, 0.9)
        call.base64_images = self.base64_images
        call.filenames = self.filenames

        self.validate(call)

        # Get fallback provider from settings
        settings_entry = None
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("provider") == "Settings":
                settings_entry = entry.data
                break
        fallback_provider = (
            settings_entry.get("fallback_provider", None) if settings_entry else None
        )
        _LOGGER.debug("Fallback provider: %s", fallback_provider)

        # Instantiate via factory
        if not isinstance(call.model, str):
            raise ServiceValidationError("invalid_model")
        try:
            provider_instance = ProviderFactory.create(
                hass=self.hass,
                provider_name=provider_name,
                config=config,
                model=call.model,
            )
        except Exception as e:
            _log_provider_failure(f"Provider factory failed for {provider_name}", e)
            raise ServiceValidationError("invalid_provider") from None

        try:
            # Make call to provider
            response_text = await provider_instance.vision_request(call)
        except Exception as e:
            _log_provider_failure(f"Provider {provider_name} failed", e)
            # Try fallback if configured and not already tried
            if (
                fallback_provider
                and fallback_provider != "no_fallback"
                and not _is_fallback_retry
                and fallback_provider != call.provider
            ):
                _LOGGER.info(f"Trying fallback provider: {fallback_provider}")
                call.provider = fallback_provider
                call.model = None
                return await self.call(call, _is_fallback_retry=True)
            else:
                if isinstance(e, ServiceValidationError):
                    # Locally raised errors carry the actionable reason.
                    raise
                raise ServiceValidationError("Provider request failed") from None
        # Handle Glimpse-v1 responses
        try:
            _LOGGER.debug("Provider %s returned a response", provider_name)
            _LOGGER.debug(f"Is Glimpse Model: {call.model_is_glimpse()}")
            if hasattr(call, "model_is_glimpse") and call.model_is_glimpse():
                try:
                    parsed = json.loads(self.heal_json(response_text))
                    result = {}
                    if isinstance(parsed, dict):
                        title_val = parsed.get("title")
                        desc_val = parsed.get("description")
                        if title_val is not None:
                            result["title"] = re.sub(
                                r"[^a-zA-Z0-9À-ÖØ-öø-ɏ\s]", "", str(title_val)
                            )
                        if desc_val is not None:
                            result["response_text"] = str(desc_val)
                        return result
                except Exception as e:
                    _LOGGER.debug(
                        "Ollama Glimpse JSON parse failed (%s)", type(e).__name__
                    )
        except Exception:
            pass

        gen_title = None
        try:
            # For structured output, extract title from JSON response if title_field is specified
            if call.response_format == "json" and call.title_field:
                try:
                    response_json = json.loads(response_text)
                    gen_title = response_json.get(call.title_field)
                except (json.JSONDecodeError, AttributeError):
                    # If JSON parsing fails or title_field not found, gen_title remains None
                    pass
            # For non-structured output, use traditional title generation
            elif call.generate_title and call.response_format != "json":
                call.message = (
                    call.memory.title_prompt
                    + "Create a title for this text: "
                    + response_text
                )
                gen_title = await provider_instance.title_request(call)
        except Exception as e:
            _log_provider_failure(
                f"Provider {provider_name} failed to generate title", e
            )
            # Try fallback if configured and not already tried
            if (
                fallback_provider
                and fallback_provider != "no_fallback"
                and not _is_fallback_retry
                and fallback_provider != call.provider
            ):
                _LOGGER.info(f"Trying fallback provider for title: {fallback_provider}")
                call.provider = fallback_provider
                call.model = None
                return await self.call(call, _is_fallback_retry=True)
            else:
                gen_title = "Event Detected"

        result = {}
        if gen_title is not None:
            result["title"] = re.sub(r"[^a-zA-Z0-9À-ÖØ-öø-ɏ\s]", "", gen_title)
        result["response_text"] = response_text

        # Handle structured response if requested
        if (
            call.response_format == "json"
            and provider_instance.supports_structured_output()
        ):
            try:
                result["structured_response"] = json.loads(response_text)
            except json.JSONDecodeError:
                # If parsing fails, return as text
                result["response_text"] = response_text
            else:
                # drop response_text if structured_response is present
                if "structured_response" in result:
                    del result["response_text"]
        else:
            result["response_text"] = response_text

        return result

    def add_frame(self, base64_image, filename):
        self.base64_images.append(base64_image)
        self.filenames.append(filename)

    def heal_json(self, text):
        """Attempt to heal malformed JSON for common LLM output issues."""
        if not isinstance(text, str):
            return text
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        healed_chars = []
        stack = []
        in_string = False
        escaped = False

        def _is_value_boundary(ch: str) -> bool:
            return ch in {",", ":", "}", "]"}

        for idx, ch in enumerate(text):
            next_char = text[idx + 1] if idx + 1 < len(text) else ""

            if in_string:
                if escaped:
                    healed_chars.append(ch)
                    escaped = False
                    continue
                if ch == "\\":
                    healed_chars.append(ch)
                    escaped = True
                    continue
                if ch == '"':
                    # If quote is likely part of the string content (e.g. 5"), escape it.
                    # Keep quote unescaped only when it looks like a real string terminator.
                    if not (
                        next_char == ""
                        or _is_value_boundary(next_char)
                        or next_char.isspace()
                    ):
                        healed_chars.append('\\"')
                        continue

                    healed_chars.append(ch)
                    in_string = False
                    continue
                healed_chars.append(ch)
                continue
            # Outside string
            if ch == '"':
                healed_chars.append(ch)
                in_string = True
                continue
            if ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in {"}", "]"}:
                if stack and stack[-1] == ch:
                    stack.pop()

            healed_chars.append(ch)
        # If the payload ends while still in a string, trailing delimiters are often
        # intended as structure (e.g. ..."description":"text}). Move those outside.
        trailing_closers = []
        if in_string:
            while stack and healed_chars and healed_chars[-1] == stack[-1]:
                trailing_closers.append(healed_chars.pop())
                stack.pop()
        # Close unterminated string first, then close open containers.
        if in_string:
            healed_chars.append('"')
        while trailing_closers:
            healed_chars.append(trailing_closers.pop())
        while stack:
            healed_chars.append(stack.pop())
        healed = "".join(healed_chars)
        try:
            json.loads(healed)
            return healed
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(healed):
            while idx < len(healed) and healed[idx].isspace():
                idx += 1
            if idx >= len(healed):
                break
            if healed[idx] not in "{[":
                idx += 1
                continue
            try:
                _, end_idx = decoder.raw_decode(healed, idx)
            except json.JSONDecodeError:
                idx += 1
                continue
            return healed[idx:end_idx]

        return text


class Provider(ABC):
    """
    Abstract base class for providers

    Args:
        hass (object): Home Assistant instance
        api_key (str, optional): API key for the provider, defaults to ""
        endpoint (dict, optional): Endpoint configuration for the provider
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        model: str,
        endpoint={
            "base_url": "",
            "deployment": "",
            "api_version": "",
            "ip_address": "",
            "port": "",
            "https": False,
        },
    ):
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.request_timeout = self._resolve_request_timeout()
        _LOGGER.debug("Provider initialized: %s", self.__class__.__name__)

    @abstractmethod
    async def _make_request(self, data: dict) -> str:
        pass

    @abstractmethod
    def _prepare_vision_data(self, call: Any) -> dict:
        pass

    @abstractmethod
    def _prepare_text_data(self, call: Any) -> dict:
        pass

    @abstractmethod
    async def validate(self) -> None | ServiceValidationError:
        pass

    def supports_structured_output(self) -> bool:
        """Return True if provider supports structured output."""
        return False

    def _get_default_parameters(self, call: Any) -> dict:
        """Get default parameters from config entry"""
        entry_id = call.provider
        domain_data = self.hass.data.get(DOMAIN) or {}

        config = domain_data.get(entry_id) or {}
        default_parameters = {
            "temperature": config.get(CONF_TEMPERATURE, 0.5),
            "top_p": config.get(CONF_TOP_P, 0.95),
            "keep_alive": config.get(CONF_KEEP_ALIVE, 5),
            "context_window": config.get(CONF_CONTEXT_WINDOW, 4096),
            "thinking_budget": config.get(CONF_THINKING_BUDGET, 0),
            "think": config.get(CONF_THINK, False),
            "reasoning_effort": config.get(CONF_REASONING_EFFORT, "none"),
        }
        if call.model_is_glimpse():
            default_parameters["temperature"] = 0.2
            default_parameters["top_p"] = 0.95
        return default_parameters

    def _get_system_prompt(self) -> str:
        """Fetch system prompt from the Settings config entry stored in hass.data."""
        domain_data = self.hass.data.get(DOMAIN) or {}
        for _, data in domain_data.items():
            if data.get(CONF_PROVIDER) == "Settings":
                return data.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT)
        return DEFAULT_SYSTEM_PROMPT

    def _get_title_prompt(self) -> str:
        """Fetch title prompt from the Settings config entry stored in hass.data."""
        domain_data = self.hass.data.get(DOMAIN) or {}
        for _, data in domain_data.items():
            if data.get(CONF_PROVIDER) == "Settings":
                return data.get(CONF_TITLE_PROMPT, DEFAULT_TITLE_PROMPT)
        return DEFAULT_TITLE_PROMPT

    def _resolve_request_timeout(self) -> int:
        """Resolve request timeout (seconds) from the Settings config entry stored in hass.data."""
        domain_data = self.hass.data.get(DOMAIN) or {}
        for _, data in domain_data.items():
            if data.get(CONF_PROVIDER) == "Settings":
                timeout = data.get(CONF_REQUEST_TIMEOUT, 60)
                try:
                    timeout_int = int(timeout)
                    return timeout_int if timeout_int > 0 else 60
                except (TypeError, ValueError):
                    return 60
        return 60

    async def vision_request(self, call: dict) -> str:
        data = self._prepare_vision_data(call)
        return await self._make_request(data)

    async def title_request(self, call: Any) -> str:
        if isinstance(call, dict):
            call["max_tokens"] = 4096
        else:
            call.max_tokens = 4096
        data = self._prepare_text_data(call)
        return await self._make_request(data)

    async def _post(self, url: str, headers: dict, data: dict) -> dict:
        """Post data to url and return response data"""
        # URLs, headers, payloads, responses and exceptions may contain secrets.
        _LOGGER.debug("Sending provider request")
        try:
            response = await self.session.post(
                url,
                headers=headers,
                json=data,
                timeout=ClientTimeout(total=self.request_timeout),
            )
        except Exception as e:
            _LOGGER.error("Provider request failed (%s)", type(e).__name__)
            raise ServiceValidationError("Provider request failed") from None

        if response.status != 200:
            _LOGGER.warning("Provider request failed (HTTP %s)", response.status)
            raise ServiceValidationError(
                f"Provider request failed (HTTP {response.status})"
            )
        try:
            return await response.json()
        except Exception as e:
            _LOGGER.error("Provider response could not be read (%s)", type(e).__name__)
            raise ServiceValidationError(
                "Provider response could not be read"
            ) from None

    async def _resolve_error(self, response, provider: str) -> str:
        """Translate response status to error message for both HTTP and SDK responses"""
        # Try to get text body if response is aiohttp
        try:
            if hasattr(response, "text"):
                full_response_text = await response.text()
            else:
                # Fallback for dict responses from SDKs (boto3 from AWS)
                full_response_text = json.dumps(response)
        except Exception:
            full_response_text = str(response)

        # Try to parse JSON
        try:
            response_json = json.loads(full_response_text)
        except Exception:
            response_json = {} if not isinstance(response, dict) else response

        try:
            if provider == "anthropic":
                error_info = response_json.get("error", {})
                return f"{error_info.get('type', 'Unknown error')}: {error_info.get('message', 'Unknown error')}"
            elif provider == "ollama":
                return response_json.get("error", "Unknown error")
            else:
                error_info = response_json.get("error", response_json)
                if isinstance(error_info, dict):
                    return (
                        error_info.get("message")
                        or error_info.get("Message")
                        or error_info.get("errorMessage")
                        or "Unknown error"
                    )
                return str(error_info) if error_info else "Unknown error"
        except Exception:
            return "Unknown error"


class OpenAI(Provider):

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        model: str,
        endpoint={"base_url": ENDPOINT_OPENAI},
    ):
        super().__init__(hass, api_key, model, endpoint=endpoint)

    def supports_structured_output(self) -> bool:
        """OpenAI supports structured output via JSON Schema."""
        return True

    def _apply_model_parameters(self, payload: dict, parameters: dict) -> dict:
        """Apply the model's reasoning and sampling rules to a request payload."""
        model = get(self.model)
        if model is UNKNOWN:
            # OpenAI-compatible servers may use unrelated model names.
            return payload

        effort = model.resolve_effort(parameters.get("reasoning_effort", "none"))
        if effort is not None:
            # Omitting `none` would enable the API's default reasoning effort.
            payload["reasoning_effort"] = effort

        # Sampling controls are incompatible with reasoning, including the API
        # default that models without a lower effort fall back to.
        if not model.supports("temperature") or effort != "none":
            payload.pop("temperature", None)
            payload.pop("top_p", None)
        return payload

    def _generate_headers(self) -> dict:
        return {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }

    def _get_request_url(self) -> str:
        if isinstance(self.endpoint, dict):
            url = self.endpoint.get("base_url")
        else:
            url = self.endpoint

        if not isinstance(url, str):
            raise ServiceValidationError("invalid_endpoint")

        normalized_url = url.rstrip("/")
        if normalized_url.endswith("/v1"):
            return f"{normalized_url}/chat/completions"

        return url

    async def _make_request(self, data: dict) -> str:
        headers = self._generate_headers()
        url = self._get_request_url()

        response = await self._post(url=url, headers=headers, data=data)
        choices = response.get("choices") if isinstance(response, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ServiceValidationError("empty_response")
        first_choice = choices[0] if isinstance(choices[0], dict) else None
        if not isinstance(first_choice, dict):
            raise ServiceValidationError("invalid_response")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ServiceValidationError("invalid_response")
        response_text = message.get("content")
        if first_choice.get("finish_reason") == "length":
            raise _CompletionResponseError(token_limit=True)
        if not isinstance(response_text, str):
            raise ServiceValidationError("invalid_response")
        if not response_text.strip():
            raise _CompletionResponseError()
        return response_text

    def _prepare_vision_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": []}],
            "max_completion_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

        payload = self._apply_model_parameters(payload, default_parameters)

        # Add structured output format if requested
        if call.response_format == "json" and call.structure:
            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                # Add additionalProperties: false to schema for OpenAI strict mode
                if "additionalProperties" not in schema:
                    schema["additionalProperties"] = False

                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": schema,
                        "strict": True,
                    },
                }
            except json.JSONDecodeError:
                # If schema is invalid, don't add structured output
                pass

        for image, filename in zip(call.base64_images, call.filenames):
            tag = (
                ("Image " + str(call.base64_images.index(image) + 1))
                if filename == ""
                else filename
            )
            payload["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"}
            )
            payload["messages"][0]["content"].append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                }
            )

        # User message
        payload["messages"][0]["content"].append({"type": "text", "text": call.message})
        # System prompt
        system_prompt = self._get_system_prompt()
        payload["messages"].insert(0, {"role": "system", "content": system_prompt})

        # Memory if use_memory is set
        if getattr(call, "use_memory", False):
            memory_content = call.memory._get_memory_images(memory_type="OpenAI")
            if memory_content:
                payload["messages"].insert(
                    1, {"role": "user", "content": memory_content}
                )

        return payload

    def _prepare_text_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": title_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "max_completion_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

        return self._apply_model_parameters(payload, default_parameters)

    async def validate(self) -> None | ServiceValidationError:
        if self.api_key:
            headers = self._generate_headers()
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": "Hi"}]}
                ],
            }
            await self._post(url=self._get_request_url(), headers=headers, data=data)
        else:
            raise ServiceValidationError("empty_api_key")


class Mistral(OpenAI):
    """Mistral (https://docs.mistral.ai/api/). OpenAI-compatible but rejects
    unknown fields, so rename max_completion_tokens to max_tokens."""

    def __init__(self, hass: HomeAssistant, api_key: str, model: str):
        super().__init__(hass, api_key, model, endpoint={"base_url": ENDPOINT_MISTRAL})

    @staticmethod
    def _rename_token_field(payload: dict) -> dict:
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        return payload

    def _prepare_vision_data(self, call: Any) -> dict:
        return self._rename_token_field(super()._prepare_vision_data(call))

    def _prepare_text_data(self, call: Any) -> dict:
        return self._rename_token_field(super()._prepare_text_data(call))


class AzureOpenAI(Provider):

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        model: str,
        endpoint={
            "base_url": ENDPOINT_AZURE,
            "endpoint": "",
            "deployment": "",
            "api_version": "",
        },
    ):
        super().__init__(hass, api_key, model, endpoint)

    def _generate_headers(self) -> dict:
        return {"Content-type": "application/json", "api-key": self.api_key}

    def _uses_completion_tokens(self) -> bool:
        """Return True when Azure expects max_completion_tokens (gpt-5 family)."""
        return "gpt-5" in (self.model or "").lower()

    async def _make_request(self, data: dict) -> str:
        headers = self._generate_headers()
        endpoint = self.endpoint.get("base_url").format(
            base_url=self.endpoint.get("endpoint"),
            deployment=self.endpoint.get("deployment"),
            api_version=self.endpoint.get("api_version"),
        )

        response = await self._post(url=endpoint, headers=headers, data=data)
        choices = response.get("choices") if isinstance(response, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ServiceValidationError("empty_response")
        first_choice = choices[0] if isinstance(choices[0], dict) else None
        if not isinstance(first_choice, dict):
            raise ServiceValidationError("invalid_response")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ServiceValidationError("invalid_response")
        response_text = message.get("content")
        if response_text is None:
            raise ServiceValidationError("invalid_response")
        return response_text

    def _prepare_vision_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        payload = {
            "messages": [{"role": "user", "content": []}],
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
            "stream": False,
        }

        if self._uses_completion_tokens():
            payload.pop("temperature", None)
            payload.pop("top_p", None)
            payload["max_completion_tokens"] = call.max_tokens
        else:
            payload["max_tokens"] = call.max_tokens
        for image, filename in zip(call.base64_images, call.filenames):
            tag = (
                ("Image " + str(call.base64_images.index(image) + 1))
                if filename == ""
                else filename
            )
            payload["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"}
            )
            payload["messages"][0]["content"].append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                }
            )
        # User message
        payload["messages"][0]["content"].append({"type": "text", "text": call.message})
        # System prompt
        system_prompt = self._get_system_prompt()
        payload["messages"].insert(0, {"role": "system", "content": system_prompt})

        # Memory if use_memory is set
        if getattr(call, "use_memory", False):
            memory_content = call.memory._get_memory_images(memory_type="OpenAI")
            if memory_content:
                payload["messages"].insert(
                    1, {"role": "user", "content": memory_content}
                )

        # Add structured output format if requested
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                # Add additionalProperties: false to schema for OpenAI strict mode
                if "additionalProperties" not in schema:
                    schema["additionalProperties"] = False

                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": schema,
                        "strict": True,
                    },
                }
            except json.JSONDecodeError:
                # If schema is invalid, don't add structured output
                pass
        return payload

    def _prepare_text_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        payload = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": title_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
            "stream": False,
        }

        if self._uses_completion_tokens():
            payload.pop("temperature", None)
            payload.pop("top_p", None)
            payload["max_completion_tokens"] = call.max_tokens
        else:
            payload["max_tokens"] = call.max_tokens

        # Add structured output format if requested
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                # Add additionalProperties: false to schema for OpenAI strict mode
                if "additionalProperties" not in schema:
                    schema["additionalProperties"] = False

                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": schema,
                        "strict": True,
                    },
                }
            except json.JSONDecodeError:
                # If schema is invalid, don't add structured output
                pass
        return payload

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")

        endpoint = self.endpoint.get("base_url").format(
            base_url=self.endpoint.get("endpoint"),
            deployment=self.endpoint.get("deployment"),
            api_version=self.endpoint.get("api_version"),
        )
        headers = self._generate_headers()
        data = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
            "stream": False,
        }
        await self._post(url=endpoint, headers=headers, data=data)

    def supports_structured_output(self) -> bool:
        """AzureOpenAI supports structured output via JSON Schema (OpenAI-compatible)."""
        return True


class Anthropic(Provider):

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        model: str,
        endpoint={"base_url": ENDPOINT_ANTHROPIC},
    ):
        super().__init__(hass, api_key, model, endpoint=endpoint)

    def supports_structured_output(self) -> bool:
        """Return True if provider supports structured output."""
        return True

    def _generate_headers(self) -> dict:
        return {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": VERSION_ANTHROPIC,
        }

    def _get_request_url(self) -> str:
        """Resolve the messages endpoint, honoring a custom API base if configured.

        Accepts a bare host (``https://proxy.example.com``), a versioned base
        (``.../v1``) or a full messages endpoint (``.../v1/messages``) and
        normalizes it to the Anthropic ``/v1/messages`` path.
        """
        if isinstance(self.endpoint, dict):
            url = self.endpoint.get("base_url") or ENDPOINT_ANTHROPIC
        else:
            url = self.endpoint or ENDPOINT_ANTHROPIC

        if not isinstance(url, str) or not url.strip():
            return ENDPOINT_ANTHROPIC

        normalized_url = url.strip().rstrip("/")
        if normalized_url.endswith("/messages"):
            return normalized_url
        if normalized_url.endswith("/v1"):
            return f"{normalized_url}/messages"
        return f"{normalized_url}/v1/messages"

    async def _make_request(self, data: dict) -> str:
        headers = self._generate_headers()
        response = await self._post(
            url=self._get_request_url(), headers=headers, data=data
        )

        content = response.get("content")
        if not isinstance(content, list):
            raise ServiceValidationError("invalid_response")

        # Anthropic returns two blocks if thinking is enabled, so loop over all of them
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return json.dumps(block.get("input", {}))

        text = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text:
            raise ServiceValidationError("empty_response")

        return text

    def _apply_parameters(self, payload: dict, call: Any) -> dict:
        parameters = self._get_default_parameters(call)
        raw_budget = parameters.get("thinking_budget", 0)

        try:
            numeric_budget = float(raw_budget)
        except (TypeError, ValueError):
            raise ServiceValidationError("Anthropic thinking budget must be an integer")

        if not numeric_budget.is_integer() or numeric_budget < 0:
            raise ServiceValidationError(
                "Anthropic thinking budget must be a non-negative integer"
            )

        budget = int(numeric_budget)
        thinking = get(self.model).thinking
        tool_choice = payload.get("tool_choice") or {}
        forced_tool = tool_choice.get("type") in {"any", "tool"}

        # The 2026-10-21 API version rejects sampling parameters on every model.
        for parameter in SAMPLING_PARAMS:
            payload.pop(parameter, None)

        if forced_tool and not thinking.forced_tool_choice:
            # These models reject forced tool use entirely.
            payload["tool_choice"] = {"type": "auto"}
            forced_tool = False

        if budget == 0:
            if thinking.between_tools:
                payload["thinking"] = {"type": "between_tools"}
            elif thinking.can_disable:
                payload["thinking"] = {"type": "disabled"}
            else:
                payload.pop("thinking", None)
            return payload

        if thinking.manual and not forced_tool:
            # An explicit budget wins where extended thinking still exists.
            if budget < 1024:
                raise ServiceValidationError(
                    "Anthropic thinking budget must be 0 or at least 1024"
                )

            try:
                max_tokens = int(payload["max_tokens"])
            except (KeyError, TypeError, ValueError):
                raise ServiceValidationError("Anthropic max_tokens must be an integer")

            if budget >= max_tokens:
                raise ServiceValidationError(
                    "Anthropic thinking budget must be less than max_tokens"
                )

            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget,
            }
            return payload

        if thinking.adaptive:
            # Adaptive thinking permits forced tool use.
            payload["thinking"] = {"type": "adaptive"}
            return payload

        if not thinking.manual:
            raise ServiceValidationError(
                f"Extended thinking is not supported by {self.model}"
            )

        # Extended thinking only allows tool_choice auto/none.
        payload["thinking"] = {"type": "disabled"}
        return payload

    def _prepare_vision_data(self, call: Any) -> dict:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": []}],
            "max_tokens": call.max_tokens,
        }

        # Add structured output support using tools
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                # Create a tool that returns the structured data
                payload["tools"] = [
                    {
                        "name": "return_structured_data",
                        "description": "Return the analysis results in the specified JSON format",
                        "input_schema": schema,
                    }
                ]
                payload["tool_choice"] = {
                    "type": "tool",
                    "name": "return_structured_data",
                }
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )
        for image, filename in zip(call.base64_images, call.filenames):
            tag = (
                ("Image " + str(call.base64_images.index(image) + 1))
                if filename == ""
                else filename
            )
            payload["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"}
            )
            payload["messages"][0]["content"].append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": f"{image}",
                    },
                }
            )
        # User message
        payload["messages"][0]["content"].append({"type": "text", "text": call.message})
        # System prompt
        payload["system"] = self._get_system_prompt()

        # Memory images if use_memory is set
        if getattr(call, "use_memory", False):
            memory_content = call.memory._get_memory_images(memory_type="Anthropic")
            if memory_content:
                payload["messages"].insert(
                    0, {"role": "user", "content": memory_content}
                )
        return self._apply_parameters(payload, call)

    def _prepare_text_data(self, call: Any) -> dict:
        title_prompt = self._get_title_prompt()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": title_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "max_tokens": call.max_tokens,
        }

        # Add structured output support using tools
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                # Create a tool that returns the structured data
                payload["tools"] = [
                    {
                        "name": "return_structured_data",
                        "description": "Return the analysis results in the specified JSON format",
                        "input_schema": schema,
                    }
                ]
                payload["tool_choice"] = {
                    "type": "tool",
                    "name": "return_structured_data",
                }
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )

        return self._apply_parameters(payload, call)

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")

        header = self._generate_headers()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1,
        }
        await self._post(url=self._get_request_url(), headers=header, data=payload)


class Google(Provider):
    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        model: str,
        endpoint={"base_url": ENDPOINT_GOOGLE},
    ):
        super().__init__(hass, api_key, model, endpoint)

    def supports_structured_output(self) -> bool:
        """Return True if provider supports structured output."""
        return True

    def _apply_thinking_config(self, generation_config: dict, parameters: dict) -> None:
        """Add the thinking control the configured model accepts."""
        model = get(self.model)
        requested = parameters.get("reasoning_effort", "none")
        if model.supports("thinking_level") and normalize_effort(requested) != "none":
            level = model.resolve_effort(requested)
            if level is not None:
                generation_config["thinkingConfig"] = {"thinkingLevel": level}
                return
        budget = parameters.get("thinking_budget", 0)
        if model.supports("thinking_budget") and isinstance(budget, (int, float)):
            if budget > 0:
                generation_config["thinkingConfig"] = {"thinkingBudget": budget}

    def _generate_headers(self) -> dict:
        return {"content-type": "application/json"}

    async def _make_request(self, data) -> str:
        try:
            endpoint = self.endpoint.get("base_url").format(
                model=self.model, api_key=self.api_key
            )
            headers = self._generate_headers()
            response = await self._post(url=endpoint, headers=headers, data=data)
            candidates = response.get("candidates")
            if not candidates or not isinstance(candidates, list) or not candidates[0]:
                raise ServiceValidationError(
                    "No candidates were returned from Google API"
                )
            content = candidates[0].get("content")
            if not content or not content.get("parts") or not content.get("parts")[0]:
                raise ServiceValidationError(
                    "No content parts were returned from Google API"
                )
            response_text = content.get("parts")[0].get("text")
        except Exception as e:
            _LOGGER.error("Google request failed (%s)", type(e).__name__)
            raise ServiceValidationError("Google request failed") from None
        return response_text

    def _prepare_vision_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        model = get(self.model)
        generation_config: dict = {"maxOutputTokens": call.max_tokens}
        if model.supports("temperature"):
            generation_config["temperature"] = default_parameters.get("temperature")
        if model.supports("top_p"):
            generation_config["topP"] = default_parameters.get("top_p")
        payload = {
            "contents": [{"role": "user", "parts": []}],
            "generationConfig": generation_config,
        }

        self._apply_thinking_config(generation_config, default_parameters)

        # Add structured output support
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                payload["generationConfig"]["response_mime_type"] = "application/json"
                payload["generationConfig"]["response_json_schema"] = schema
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )
        for image, filename in zip(call.base64_images, call.filenames):
            tag = (
                ("Image " + str(call.base64_images.index(image) + 1))
                if filename == ""
                else filename
            )
            payload["contents"][0]["parts"].append({"text": tag + ":"})
            payload["contents"][0]["parts"].append(
                {"inline_data": {"mime_type": "image/jpeg", "data": image}}
            )
        # User message
        payload["contents"][0]["parts"].append({"text": call.message})
        # System prompt
        system_prompt = self._get_system_prompt()
        payload["contents"].insert(
            0, {"role": "user", "parts": [{"text": system_prompt}]}
        )
        # Memory if use_memory is set
        if getattr(call, "use_memory", False):
            memory_content = call.memory._get_memory_images(memory_type="Google")
            if memory_content:
                payload["contents"].insert(0, {"role": "user", "parts": memory_content})

        return payload

    def _prepare_text_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        model = get(self.model)
        generation_config: dict = {"maxOutputTokens": call.max_tokens}
        if model.supports("temperature"):
            generation_config["temperature"] = default_parameters.get("temperature")
        if model.supports("top_p"):
            generation_config["topP"] = default_parameters.get("top_p")
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": title_prompt}]},
                {"role": "user", "parts": [{"text": call.message}]},
            ],
            "generationConfig": generation_config,
        }

        self._apply_thinking_config(generation_config, default_parameters)

        # Add structured output support
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                payload["generationConfig"]["response_mime_type"] = "application/json"
                payload["generationConfig"]["response_json_schema"] = schema
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )

        return payload

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")

        headers = self._generate_headers()
        data = {
            "contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
            "generationConfig": {"maxOutputTokens": 1, "temperature": 0.5},
        }
        await self._post(
            url=self.endpoint.get("base_url").format(
                model=self.model, api_key=self.api_key
            ),
            headers=headers,
            data=data,
        )


class Groq(Provider):

    def __init__(self, hass: HomeAssistant, api_key: str, model: str):
        super().__init__(hass, api_key, model)

    def _generate_headers(self) -> dict:
        return {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }

    async def _make_request(self, data: dict) -> str:
        headers = self._generate_headers()
        response = await self._post(url=ENDPOINT_GROQ, headers=headers, data=data)

        choices = response.get("choices") if isinstance(response, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ServiceValidationError("empty_response")

        first_choice = choices[0] if isinstance(choices[0], dict) else None
        if not isinstance(first_choice, dict):
            raise ServiceValidationError("invalid_response")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ServiceValidationError("invalid_response")

        response_text = message.get("content")
        if response_text is None:
            raise ServiceValidationError("invalid_response")

        return response_text

    def _prepare_vision_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        first_image = call.base64_images[0]
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": call.message},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{first_image}"
                            },
                        },
                    ],
                }
            ],
            "model": self.model,
            "max_completion_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

        payload["messages"].insert(
            0, {"role": "system", "content": self._get_system_prompt()}
        )
        # Groq does not support multiple images, so no memory

        # Add structured output format if requested
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": schema,
                        "strict": False,  # Groq doesn't support strict mode like OpenAI
                    },
                }
            except json.JSONDecodeError:
                # If schema is invalid, don't add structured output
                pass
        return payload

    def _prepare_text_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        payload = {
            "messages": [
                {"role": "system", "content": title_prompt},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "model": self.model,
            "max_completion_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

        # Add structured output format if requested
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": schema,
                        "strict": False,  # Groq doesn't support strict mode like OpenAI
                    },
                }
            except json.JSONDecodeError:
                # If schema is invalid, don't add structured output
                pass

        return payload

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")
        headers = self._generate_headers()
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
        }
        await self._post(url=ENDPOINT_GROQ, headers=headers, data=data)

    def supports_structured_output(self) -> bool:
        """Groq supports structured output via OpenAI-compatible JSON schema."""
        return True


class LocalAI(Provider):

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        model: str,
        endpoint={"ip_address": "", "port": "", "https": False},
    ):
        super().__init__(hass, api_key, model, endpoint)

    async def _make_request(self, data) -> str:
        endpoint = ENDPOINT_LOCALAI.format(
            protocol="https" if self.endpoint.get("https") else "http",
            ip_address=self.endpoint.get("ip_address"),
            port=self.endpoint.get("port"),
        )

        headers = {}
        response = await self._post(url=endpoint, headers=headers, data=data)
        if not isinstance(response, dict):
            raise ServiceValidationError("invalid_response")

        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ServiceValidationError("empty_response")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ServiceValidationError("invalid_response")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ServiceValidationError("invalid_response")

        response_text = message.get("content")
        if response_text is None:
            raise ServiceValidationError("invalid_response")

        return response_text

    def _prepare_vision_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": []}],
            "max_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }
        for image, filename in zip(call.base64_images, call.filenames):
            tag = (
                ("Image " + str(call.base64_images.index(image) + 1))
                if filename == ""
                else filename
            )
            payload["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"}
            )
            payload["messages"][0]["content"].append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                }
            )
        # User message
        payload["messages"][0]["content"].append({"type": "text", "text": call.message})
        # System prompt
        payload["messages"].insert(
            0, {"role": "system", "content": self._get_system_prompt()}
        )

        # Memory if use_memory is set
        if getattr(call, "use_memory", False):
            memory_content = call.memory._get_memory_images(memory_type="OpenAI")
            if memory_content:
                payload["messages"].insert(
                    1, {"role": "user", "content": memory_content}
                )

        # Add structured output support (OpenAI-compatible)
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": schema,
                        "strict": False,  # LocalAI may not support strict mode
                    },
                }
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )
        return payload

    def _prepare_text_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": title_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "max_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

        # Add structured output support (OpenAI-compatible)
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "schema": schema,
                        "strict": False,  # LocalAI may not support strict mode
                    },
                }
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )

        return payload

    async def validate(self) -> None | ServiceValidationError:
        if not self.endpoint.get("ip_address") or not self.endpoint.get("port"):
            raise ServiceValidationError("handshake_failed")
        session = async_get_clientsession(self.hass)
        ip_address = self.endpoint.get("ip_address")
        port = self.endpoint.get("port")
        protocol = "https" if self.endpoint.get("https") else "http"

        try:
            response = await session.get(f"{protocol}://{ip_address}:{port}/readyz")
            if response.status != 200:
                raise ServiceValidationError("handshake_failed")
        except Exception:
            raise ServiceValidationError("handshake_failed") from None

    def supports_structured_output(self) -> bool:
        """LocalAI supports structured output via OpenAI-compatible JSON schema format."""
        return True


class Ollama(Provider):

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        model: str,
        endpoint={"ip_address": "0.0.0.0", "port": "11434", "https": False},
    ):
        super().__init__(hass, api_key, model, endpoint)

    def supports_structured_output(self) -> bool:
        """Return True if provider supports structured output."""
        return True

    def _model_supports_thinking(self) -> bool:
        thinking_models = ["qwen3.5", "qwen3-vl"]
        return any(
            thinking_model in self.model.lower() for thinking_model in thinking_models
        )

    async def _make_request(self, data: dict) -> str:
        https = self.endpoint.get("https")
        ip_address = self.endpoint.get("ip_address")
        port = self.endpoint.get("port")
        protocol = "https" if https else "http"
        endpoint = ENDPOINT_OLLAMA.format(
            ip_address=ip_address, port=port, protocol=protocol
        )

        response = await self._post(url=endpoint, headers={}, data=data)
        if not isinstance(response, dict):
            raise ServiceValidationError("invalid_response")
        response_text = response.get("message", {}).get("content")
        if response_text is None:
            raise ServiceValidationError("invalid_response")
        return response_text

    def _prepare_vision_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        payload = {
            "model": self.model,
            "system": self._get_system_prompt() if not call.model_is_glimpse() else "",
            "messages": [
                {
                    "role": "user",
                    "content": (
                        call.message
                        if not call.model_is_glimpse()
                        else GLIMPSE_V1_INSTRUCTIONS
                    ),
                    "images": call.base64_images,
                },
            ],
            "prompt": (),
            "images": call.base64_images,
            "stream": False,
            "keep_alive": default_parameters.get("keep_alive"),
            "think": default_parameters.get("think", False)
            and self._model_supports_thinking(),
            "options": {
                "num_predict": call.max_tokens,
                "temperature": default_parameters.get("temperature"),
                "top_p": default_parameters.get("top_p"),
                "num_ctx": default_parameters.get("context_window"),
            },
        }

        # Add structured output support
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )
                payload["format"] = schema
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )

        # Memory if use_memory is set
        if getattr(call, "use_memory", False):
            memory_content = call.memory._get_memory_images(memory_type="Ollama")
            if memory_content:
                payload["messages"].extend(memory_content)

        return payload

    def _prepare_text_data(self, call: Any) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": title_prompt},
                {"role": "user", "content": call.message},
            ],
            "stream": False,
            "keep_alive": default_parameters.get("keep_alive", "5m"),
            "think": default_parameters.get("think", False)
            and self._model_supports_thinking(),
            "options": {
                "num_predict": call.max_tokens,
                "temperature": default_parameters.get("temperature"),
                "top_p": default_parameters.get("top_p"),
                "num_ctx": default_parameters.get("context_window"),
            },
        }

        # Add structured output support
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )
                payload["format"] = schema
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )

        return payload

    async def validate(self) -> None | ServiceValidationError:
        if not self.endpoint.get("ip_address") or not self.endpoint.get("port"):
            raise ServiceValidationError("handshake_failed")
        session = async_get_clientsession(self.hass)
        ip_address = self.endpoint.get("ip_address")
        port = self.endpoint.get("port")
        protocol = "https" if self.endpoint.get("https") else "http"

        try:
            _LOGGER.info("Checking Ollama connection")
            response = await session.get(
                f"{protocol}://{ip_address}:{port}/api/tags", headers={}
            )
            _LOGGER.debug("Ollama connection response received")
            if response.status != 200:
                raise ServiceValidationError("handshake_failed")
        except Exception as e:
            _LOGGER.error("Ollama connection failed (%s)", type(e).__name__)
            raise ServiceValidationError("handshake_failed") from None


class AWSBedrock(Provider):

    def __init__(
        self,
        hass: HomeAssistant,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        aws_region_name: str,
        model: str,
        api_key: str | None = None,
    ):
        # If api_key is provided, use Bearer token authentication
        # Otherwise, use traditional IAM credentials
        if api_key:
            super().__init__(hass=hass, api_key=api_key, model=model)
            self.aws_region = aws_region_name
            self.use_bearer_token = True
        else:
            super().__init__(hass=hass, api_key="", model=model)
            self.aws_access_key_id = aws_access_key_id
            self.aws_secret_access_key = aws_secret_access_key
            self.aws_region = aws_region_name
            self.use_bearer_token = False

    def _generate_headers(self) -> dict:
        return {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }

    def _build_inference_config(self, max_tokens: int, temperature: Any) -> dict:
        """Build the inference config supported by the configured model."""
        inference_config: dict = {"maxTokens": max_tokens}
        # Adaptive thinking models reject sampling parameters
        if not get(self.model).thinking.adaptive:
            inference_config["temperature"] = temperature
        return inference_config

    async def _make_request(self, data: dict) -> str:

        if self.use_bearer_token:
            # Use Bearer token with direct HTTP API
            headers = self._generate_headers()
            endpoint = f"https://bedrock-runtime.{self.aws_region}.amazonaws.com/model/{self.model}/converse"
            response = await self._post(url=endpoint, headers=headers, data=data)

            if not isinstance(response, dict):
                raise ServiceValidationError("invalid_response")

            output = response.get("output")
            if not isinstance(output, dict):
                raise ServiceValidationError("invalid_response")

            message = output.get("message")
            if not isinstance(message, dict):
                raise ServiceValidationError("invalid_response")

            return self._parse_message_content(message)
        else:
            # Use traditional IAM credentials with boto3
            response = await self.invoke_bedrock(model=self.model, data=data)

            if not isinstance(response, dict):
                raise ServiceValidationError("invalid_response")

            message = response.get("message")
            if not isinstance(message, dict):
                raise ServiceValidationError("invalid_response")

            return self._parse_message_content(message)

    def _parse_message_content(self, message: dict) -> str:
        """Extract the response from all message content blocks."""
        message_content = message.get("content") or []
        if not isinstance(message_content, list) or len(message_content) == 0:
            return ""

        if not all(isinstance(block, dict) for block in message_content):
            raise ServiceValidationError("invalid_response")

        # Adaptive-thinking models return a reasoningContent block before the
        # answer, so loop over all blocks instead of reading only the first
        for block in message_content:
            tool_use = block.get("toolUse")
            if isinstance(tool_use, dict):
                # Extract the structured data from tool use
                return json.dumps(tool_use.get("input", {}))

        # Regular text response
        return "".join(block.get("text", "") for block in message_content)

    async def invoke_bedrock(self, model: str, data: dict) -> dict:
        """Post data to url and return response data"""
        _LOGGER.debug("Sending AWS Bedrock request")

        try:
            _LOGGER.info(f"Invoking Bedrock model {model} in {self.aws_region}")
            client = await self.hass.async_add_executor_job(
                partial(
                    boto3.client,
                    "bedrock-runtime",
                    region_name=self.aws_region,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                )
            )

            # Invoke the model with the response stream
            converse_kwargs = {
                "modelId": model,
                "messages": data.get("messages"),
                "inferenceConfig": data.get("inferenceConfig"),
            }

            # Add toolConfig if present (for structured output)
            if "toolConfig" in data:
                converse_kwargs["toolConfig"] = data.get("toolConfig")

            # Add system prompt if present (for structured output)
            if "system" in data:
                converse_kwargs["system"] = data.get("system")

            response = await self.hass.async_add_executor_job(
                partial(client.converse, **converse_kwargs)
            )
            _LOGGER.debug("AWS Bedrock call completed")

        except Exception as e:
            _LOGGER.error("AWS Bedrock request failed (%s)", type(e).__name__)
            raise ServiceValidationError("AWS Bedrock request failed") from None

        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            status = response["ResponseMetadata"]["HTTPStatusCode"]
            _LOGGER.warning("AWS Bedrock request failed (HTTP %s)", status)
            raise ServiceValidationError(f"AWS Bedrock request failed (HTTP {status})")
        else:
            # get observability data
            metrics = response.get("metrics")
            latency = metrics.get("latencyMs")
            token_usage = response.get("usage")
            tokens_in = token_usage.get("inputTokens")
            tokens_out = token_usage.get("outputTokens")
            tokens_total = token_usage.get("totalTokens")
            _LOGGER.debug(
                f"AWS Bedrock call latency: {latency}ms inputTokens: {tokens_in} outputTokens: {tokens_out} totalTokens: {tokens_total}"
            )
            response_data = response.get("output")
            _LOGGER.debug("AWS Bedrock response received")
        return response_data

    def _prepare_vision_data(self, call: Any) -> dict:
        _LOGGER.debug(f"Found model type `{self.model}` for AWS Bedrock call.")
        default_parameters = self._get_default_parameters(call)
        # We need to generate the correct format for the respective models
        payload = {
            "messages": [{"role": "user", "content": []}],
            "inferenceConfig": self._build_inference_config(
                call.max_tokens, default_parameters.get("temperature")
            ),
        }

        # Bedrock converse API wants the raw bytes of the image
        for image, filename in zip(call.base64_images, call.filenames):
            tag = (
                ("Image " + str(call.base64_images.index(image) + 1))
                if filename == ""
                else filename
            )
            payload["messages"][0]["content"].append({"text": tag + ":"})
            payload["messages"][0]["content"].append(
                {
                    "image": {
                        "format": "jpeg",
                        "source": {"bytes": base64.b64decode(image)},
                    }
                }
            )
        # User message
        payload["messages"][0]["content"].append({"text": call.message})
        # System prompt
        payload["messages"].insert(
            0, {"role": "user", "content": [{"text": self._get_system_prompt()}]}
        )

        # Memory images only when enabled
        if getattr(call, "use_memory", False):
            memory_content = call.memory._get_memory_images(memory_type="AWS")
            if memory_content:
                payload["messages"].insert(
                    1, {"role": "user", "content": memory_content}
                )

        # Add structured output support using tool definitions
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                # Create a tool that returns the structured data
                payload["toolConfig"] = {
                    "tools": [
                        {
                            "toolSpec": {
                                "name": "return_structured_data",
                                "description": "Return the analysis results in the specified JSON format",
                                "inputSchema": {"json": schema},
                            }
                        }
                    ],
                    "toolChoice": {"tool": {"name": "return_structured_data"}},
                }
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )

        return payload

    def _prepare_text_data(self, call: Any) -> dict:
        title_prompt = self._get_title_prompt()
        payload = {
            "messages": [
                {"role": "user", "content": [{"text": title_prompt}]},
                {"role": "user", "content": [{"text": call.message}]},
            ],
            "inferenceConfig": self._build_inference_config(
                call.max_tokens, call.temperature
            ),
        }

        # Add structured output support using tool definitions
        if call.response_format == "json" and call.structure:
            import json

            try:
                schema = (
                    json.loads(call.structure)
                    if isinstance(call.structure, str)
                    else call.structure
                )

                # Create a tool that returns the structured data
                payload["toolConfig"] = {
                    "tools": [
                        {
                            "toolSpec": {
                                "name": "return_structured_data",
                                "description": "Return the analysis results in the specified JSON format",
                                "inputSchema": {"json": schema},
                            }
                        }
                    ],
                    "toolChoice": {"tool": {"name": "return_structured_data"}},
                }
            except json.JSONDecodeError as e:
                raise ServiceValidationError(
                    f"Invalid JSON in structure parameter: {str(e)}"
                )

        return payload

    async def validate(self) -> None | ServiceValidationError:
        data = {
            "messages": [{"role": "user", "content": [{"text": "Hi"}]}],
            "inferenceConfig": self._build_inference_config(10, 0.5),
        }
        await self.invoke_bedrock(model=self.model, data=data)

    def supports_structured_output(self) -> bool:
        """AWS Bedrock supports structured output via tool definitions in Converse API."""
        return True


class ProviderFactory:
    """
    Factory to create provider instances from a provider name and config
    """

    @staticmethod
    def create(
        hass: HomeAssistant, provider_name: str, config: dict, model: str
    ) -> Provider:
        if provider_name == "OpenAI":
            return OpenAI(
                hass=hass,
                api_key=cast(str, config.get(CONF_API_KEY) or ""),
                model=model,
            )

        if provider_name == "Azure":
            return AzureOpenAI(
                hass,
                api_key=cast(str, config.get(CONF_API_KEY) or ""),
                model=model,
                endpoint={
                    "base_url": ENDPOINT_AZURE,
                    "endpoint": config.get(CONF_AZURE_BASE_URL),
                    "deployment": config.get(CONF_AZURE_DEPLOYMENT),
                    "api_version": config.get(CONF_AZURE_VERSION),
                },
            )

        if provider_name == "Anthropic":
            return Anthropic(
                hass,
                api_key=cast(str, config.get(CONF_API_KEY) or ""),
                model=model,
                endpoint={
                    "base_url": config.get(CONF_ANTHROPIC_BASE_URL)
                    or ENDPOINT_ANTHROPIC
                },
            )

        if provider_name == "Google":
            return Google(
                hass,
                api_key=cast(str, config.get(CONF_API_KEY) or ""),
                model=model,
                endpoint={"base_url": ENDPOINT_GOOGLE},
            )

        if provider_name == "Groq":
            return Groq(
                hass, api_key=cast(str, config.get(CONF_API_KEY) or ""), model=model
            )

        if provider_name == "LocalAI":
            return LocalAI(
                hass,
                api_key="",
                model=model,
                endpoint={
                    "ip_address": config.get(CONF_IP_ADDRESS),
                    "port": config.get(CONF_PORT),
                    "https": config.get(CONF_HTTPS, False),
                },
            )

        if provider_name == "Ollama":
            return Ollama(
                hass,
                api_key="",
                model=model,
                endpoint={
                    "ip_address": config.get(CONF_IP_ADDRESS),
                    "port": config.get(CONF_PORT),
                    "https": config.get(CONF_HTTPS, False),
                    "keep_alive": config.get(CONF_KEEP_ALIVE, 5),
                    "context_window": config.get(CONF_CONTEXT_WINDOW, 2048),
                },
            )

        if provider_name == "Custom OpenAI":
            return OpenAI(
                hass,
                api_key=cast(str, config.get(CONF_API_KEY) or ""),
                model=model,
                endpoint={"base_url": config.get(CONF_CUSTOM_OPENAI_ENDPOINT)},
            )

        if provider_name == "AWS Bedrock":
            return AWSBedrock(
                hass,
                aws_access_key_id=cast(str, config.get(CONF_AWS_ACCESS_KEY_ID) or ""),
                aws_secret_access_key=cast(
                    str, config.get(CONF_AWS_SECRET_ACCESS_KEY) or ""
                ),
                aws_region_name=cast(str, config.get(CONF_AWS_REGION_NAME) or ""),
                model=model,
            )

        if provider_name in ("OpenWebUI", "Open WebUI"):
            endpoint = config.get(
                CONF_CUSTOM_OPENAI_ENDPOINT
            ) or ENDPOINT_OPENWEBUI.format(
                ip_address=config.get(CONF_IP_ADDRESS),
                port=config.get(CONF_PORT),
                protocol="https" if config.get(CONF_HTTPS, False) else "http",
            )
            return OpenAI(
                hass,
                api_key=cast(str, config.get(CONF_API_KEY) or ""),
                model=model,
                endpoint={"base_url": endpoint},
            )

        if provider_name == "OpenRouter":
            return OpenAI(
                hass,
                api_key=cast(str, config.get(CONF_API_KEY) or ""),
                model=model,
                endpoint={"base_url": ENDPOINT_OPENROUTER},
            )

        if provider_name == "Mistral":
            return Mistral(
                hass,
                api_key=cast(str, config.get(CONF_API_KEY) or ""),
                model=model,
            )

        raise ServiceValidationError("invalid_provider")
