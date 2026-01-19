from abc import ABC, abstractmethod
from aiohttp import ClientTimeout
import boto3
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from functools import partial
import logging
import inspect
import re
import json
import base64
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
    CONF_KEEP_ALIVE,
    CONF_CONTEXT_WINDOW,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_SYSTEM_PROMPT,
    CONF_TITLE_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TITLE_PROMPT,
)

_LOGGER = logging.getLogger(__name__)


class Request:
    def __init__(self, hass, message, max_tokens, temperature):
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
        config_entry = self.hass.data.get(DOMAIN).get(provider)
        provider_name = self.get_provider(self.hass, provider)
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
        }.get(provider_name)

    def validate(self, call) -> None | ServiceValidationError:
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

    async def call(self, call, _is_fallback_retry=False):
        """
        Forwards a request to the specified provider and optionally generates a title.
        """
        entry_id = call.provider
        config = self.hass.data.get(DOMAIN).get(entry_id)
        if config is None:
            raise ServiceValidationError(
                f"Provider config not found for entry_id: {entry_id}"
            )

        provider_name = Request.get_provider(self.hass, entry_id)
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
        try:
            provider_instance = ProviderFactory.create(
                hass=self.hass,
                provider_name=provider_name,
                config=config,
                model=call.model,
            )
        except Exception as e:
            _LOGGER.error(f"Provider factory failed for {provider_name}: {e}")
            raise ServiceValidationError("invalid_provider")

        try:
            # Make call to provider
            response_text = await provider_instance.vision_request(call)
        except Exception as e:
            _LOGGER.error(f"Provider {provider_name} failed: {e}")
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
                response_text = "Couldn't generate content. Check logs for details."

        gen_title = None
        try:
            if call.generate_title:
                call.message = (
                    call.memory.title_prompt
                    + "Create a title for this text: "
                    + response_text
                )
                gen_title = await provider_instance.title_request(call)
        except Exception as e:
            _LOGGER.error(f"Provider {provider_name} failed to generate title: {e}")
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
            result["title"] = re.sub(r"[^a-zA-Z0-9ŽžÀ-ÿ\s]", "", gen_title)
        result["response_text"] = response_text
        return result

    def add_frame(self, base64_image, filename):
        self.base64_images.append(base64_image)
        self.filenames.append(filename)


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
        hass: object,
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
        _LOGGER.debug(
            f"Provider initialized: {self.__class__.__name__.title()}(model={self.model}, endpoint={self.endpoint})"
        )

    @abstractmethod
    async def _make_request(self, data: dict) -> str:
        pass

    @abstractmethod
    def _prepare_vision_data(self, call: dict) -> dict:
        pass

    @abstractmethod
    def _prepare_text_data(self, call: dict) -> dict:
        pass

    @abstractmethod
    async def validate(self) -> None | ServiceValidationError:
        pass

    def _get_default_parameters(self, call: dict) -> dict:
        """Get default parameters from config entry"""
        entry_id = call.provider
        domain_data = self.hass.data.get(DOMAIN) or {}
        config = domain_data.get(entry_id) or {}
        default_parameters = {
            "temperature": config.get(CONF_TEMPERATURE, 0.5),
            "top_p": config.get(CONF_TOP_P, 0.9),
            "keep_alive": config.get(CONF_KEEP_ALIVE, 5),
            "context_window": config.get(CONF_CONTEXT_WINDOW, 2048),
        }
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

    async def vision_request(self, call: dict) -> str:
        data = self._prepare_vision_data(call)
        return await self._make_request(data)

    async def title_request(self, call: dict) -> str:
        call.max_tokens = 4096
        data = self._prepare_text_data(call)
        return await self._make_request(data)

    async def _post(self, url: str, headers: dict, data: dict) -> dict:
        """Post data to url and return response data"""
        _LOGGER.debug(f"Request data: {Request.sanitize_data(data)}")
        # Sanitize url
        san_url = re.sub(r"\?key=[^&]*", "", url)
        try:
            _LOGGER.debug(f"Posting to {san_url}")
            response = await self.session.post(
                url, headers=headers, json=data, timeout=ClientTimeout(total=60)
            )
        except Exception as e:
            raise ServiceValidationError(f"Request failed: {e}")

        if response.status != 200:
            frame = inspect.stack()[1]
            provider = frame.frame.f_locals["self"].__class__.__name__.lower()
            parsed_response = await self._resolve_error(response, provider)
            raise ServiceValidationError(parsed_response)
        else:
            response_data = await response.json()
            _LOGGER.debug(f"Response data: {response_data}")
            return response_data

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

        _LOGGER.debug(f"[INFO] Full Response: {full_response_text}")

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
        hass: object,
        api_key: str,
        model: str,
        endpoint={"base_url": ENDPOINT_OPENAI},
    ):
        super().__init__(hass, api_key, model, endpoint=endpoint)

    def _generate_headers(self) -> dict:
        return {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }

    async def _make_request(self, data: dict) -> str:
        headers = self._generate_headers()
        if isinstance(self.endpoint, dict):
            url = self.endpoint.get("base_url")
        else:
            url = self.endpoint
        response = await self._post(url=url, headers=headers, data=data)
        response_text = response.get("choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": []}],
            "max_completion_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

        # Remove temperature and top_p if model is gpt-5
        if self.model in ["gpt-5", "gpt-5-mini", "gpt-5-nano"]:
            payload = {
                k: v for k, v in payload.items() if k not in ("temperature", "top_p")
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

    def _prepare_text_data(self, call: dict) -> dict:
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

        # Remove temperature and top_p if model is gpt-5
        if self.model in ["gpt-5", "gpt-5-mini", "gpt-5-nano"]:
            payload = {
                k: v for k, v in payload.items() if k not in ("temperature", "top_p")
            }
        return payload

    async def validate(self) -> None | ServiceValidationError:
        if self.api_key:
            headers = self._generate_headers()
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": "Hi"}]}
                ],
            }
            await self._post(
                url=self.endpoint.get("base_url"), headers=headers, data=data
            )
        else:
            raise ServiceValidationError("empty_api_key")


class AzureOpenAI(Provider):
    def __init__(
        self,
        hass: object,
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

    async def _make_request(self, data: dict) -> str:
        headers = self._generate_headers()
        endpoint = self.endpoint.get("base_url").format(
            base_url=self.endpoint.get("endpoint"),
            deployment=self.endpoint.get("deployment"),
            api_version=self.endpoint.get("api_version"),
        )

        response = await self._post(url=endpoint, headers=headers, data=data)
        response_text = response.get("choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        payload = {
            "messages": [{"role": "user", "content": []}],
            "max_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
            "stream": False,
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

    def _prepare_text_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        return {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": title_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "max_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
            "stream": False,
        }

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
            "max_tokens": 1,
            "temperature": 0.5,
            "stream": False,
        }
        await self._post(url=endpoint, headers=headers, data=data)


class Anthropic(Provider):
    def __init__(self, hass: object, api_key: str, model: str):
        super().__init__(hass, api_key, model)

    def _generate_headers(self) -> dict:
        return {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": VERSION_ANTHROPIC,
        }

    async def _make_request(self, data: dict) -> str:
        headers = self._generate_headers()
        response = await self._post(url=ENDPOINT_ANTHROPIC, headers=headers, data=data)
        response_text = response.get("content")[0].get("text")
        return response_text

    def _prepare_vision_data(self, call: dict) -> dict:
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
        return payload

    def _prepare_text_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        return {
            "model": self.model,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": title_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "max_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")

        header = self._generate_headers()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1,
            "temperature": 0.5,
        }
        await self._post(
            url=f"https://api.anthropic.com/v1/messages", headers=header, data=payload
        )


class Google(Provider):
    def __init__(
        self,
        hass: object,
        api_key: str,
        model: str,
        endpoint={"base_url": ENDPOINT_GOOGLE},
    ):
        super().__init__(hass, api_key, model, endpoint)

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
            _LOGGER.error(f"Error: {e}")
            raise e
        return response_text

    def _prepare_vision_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        payload = {
            "contents": [{"role": "user", "parts": []}],
            "generationConfig": {
                "maxOutputTokens": call.max_tokens,
                "temperature": default_parameters.get("temperature"),
                "topP": default_parameters.get("top_p"),
            },
        }
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

    def _prepare_text_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        return {
            "contents": [
                {"role": "user", "parts": [{"text": title_prompt}]},
                {"role": "user", "parts": [{"text": call.message}]},
            ],
            "generationConfig": {
                "maxOutputTokens": call.max_tokens,
                "temperature": default_parameters.get("temperature"),
                "topP": default_parameters.get("top_p"),
            },
        }

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
    def __init__(self, hass: object, api_key: str, model: str):
        super().__init__(hass, api_key, model)

    def _generate_headers(self) -> dict:
        return {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }

    async def _make_request(self, data: dict) -> str:
        headers = self._generate_headers()
        response = await self._post(url=ENDPOINT_GROQ, headers=headers, data=data)
        response_text = response.get("choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call: dict) -> dict:
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
        return payload

    def _prepare_text_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        return {
            "messages": [
                {"role": "system", "content": title_prompt},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "model": self.model,
            "max_completion_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")
        headers = self._generate_headers()
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Hi"}],
        }
        await self._post(url=ENDPOINT_GROQ, headers=headers, data=data)


class LocalAI(Provider):
    def __init__(
        self,
        hass: object,
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
        response_text = response.get("choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call: dict) -> dict:
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
        return payload

    def _prepare_text_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        return {
            "model": self.model,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": title_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": call.message}]},
            ],
            "max_tokens": call.max_tokens,
            "temperature": default_parameters.get("temperature"),
            "top_p": default_parameters.get("top_p"),
        }

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
            raise ServiceValidationError("handshake_failed")


class Ollama(Provider):
    def __init__(
        self,
        hass: object,
        api_key: str,
        model: str,
        endpoint={"ip_address": "0.0.0.0", "port": "11434", "https": False},
    ):
        super().__init__(hass, api_key, model, endpoint)

    async def _make_request(self, data: dict) -> str:
        https = self.endpoint.get("https")
        ip_address = self.endpoint.get("ip_address")
        port = self.endpoint.get("port")
        protocol = "https" if https else "http"
        endpoint = ENDPOINT_OLLAMA.format(
            ip_address=ip_address, port=port, protocol=protocol
        )

        response = await self._post(url=endpoint, headers={}, data=data)
        response_text = response.get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        payload = {
            "model": self.model,
            "messages": [],
            "stream": False,
            "keep_alive": default_parameters.get("keep_alive"),
            "options": {
                "num_predict": call.max_tokens,
                "temperature": default_parameters.get("temperature"),
                "num_ctx": default_parameters.get("context_window"),
            },
        }

        for image, filename in zip(call.base64_images, call.filenames):
            tag = (
                ("Image " + str(call.base64_images.index(image) + 1))
                if filename == ""
                else filename
            )
            image_message = {"role": "user", "content": tag + ":", "images": [image]}
            payload["messages"].append(image_message)
        prompt_message = {"role": "user", "content": call.message}
        # User message
        payload["messages"].append(prompt_message)
        # System prompt
        payload["system"] = self._get_system_prompt()

        # Memory if use_memory is set
        if getattr(call, "use_memory", False):
            memory_content = call.memory._get_memory_images(memory_type="Ollama")
            if memory_content:
                payload["messages"].extend(memory_content)

        return payload

    def _prepare_text_data(self, call: dict) -> dict:
        default_parameters = self._get_default_parameters(call)
        title_prompt = self._get_title_prompt()
        return {
            "model": self.model,
            "messages": [
                {"role": "user", "content": title_prompt},
                {"role": "user", "content": call.message},
            ],
            "stream": False,
            "keep_alive": default_parameters.get("keep_alive", "5m"),
            "options": {
                "num_predict": call.max_tokens,
                "temperature": default_parameters.get("temperature"),
                "num_ctx": default_parameters.get("context_window"),
            },
        }

    async def validate(self) -> None | ServiceValidationError:
        if not self.endpoint.get("ip_address") or not self.endpoint.get("port"):
            raise ServiceValidationError("handshake_failed")
        session = async_get_clientsession(self.hass)
        ip_address = self.endpoint.get("ip_address")
        port = self.endpoint.get("port")
        protocol = "https" if self.endpoint.get("https") else "http"

        try:
            _LOGGER.info(f"Checking connection to {protocol}://{ip_address}:{port}")
            response = await session.get(
                f"{protocol}://{ip_address}:{port}/api/tags", headers={}
            )
            _LOGGER.debug(f"Response: {response}")
            if response.status != 200:
                raise ServiceValidationError("handshake_failed")
        except Exception as e:
            _LOGGER.error(f"Error: {e}")
            raise ServiceValidationError("handshake_failed")


class AWSBedrock(Provider):
    def __init__(
        self,
        hass: object,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        aws_region_name: str,
        model: str,
    ):
        super().__init__(hass=hass, api_key="", model=model)
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region_name

    def _generate_headers(self) -> dict:
        return {
            "Content-type": "application/json",
            "Authorization": "Bearer " + self.api_key,
        }

    async def _make_request(self, data: dict) -> str:
        response = await self.invoke_bedrock(model=self.model, data=data)
        response_text = response.get("message").get("content")[0].get("text")
        return response_text

    async def invoke_bedrock(self, model: str, data: dict) -> dict:
        """Post data to url and return response data"""
        _LOGGER.debug(f"AWS Bedrock request data: {Request.sanitize_data(data)}")

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
            response = await self.hass.async_add_executor_job(
                partial(
                    client.converse,
                    modelId=model,
                    messages=data.get("messages"),
                    inferenceConfig=data.get("inferenceConfig"),
                )
            )
            _LOGGER.debug(f"AWS Bedrock call Response: {response}")

        except Exception as e:
            raise ServiceValidationError(f"Request failed: {e}")

        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            frame = inspect.stack()[1]
            provider = frame.frame.f_locals["self"].__class__.__name__.lower()
            parsed_response = await self._resolve_error(response, provider)
            raise ServiceValidationError(parsed_response)
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
            _LOGGER.debug(f"AWS Bedrock call response data: {response_data}")
            return response_data

    def _prepare_vision_data(self, call: dict) -> dict:
        _LOGGER.debug(f"Found model type `{self.model}` for AWS Bedrock call.")
        default_parameters = self._get_default_parameters(call)
        # We need to generate the correct format for the respective models
        payload = {
            "messages": [{"role": "user", "content": []}],
            "inferenceConfig": {
                "maxTokens": call.max_tokens,
                "temperature": default_parameters.get("temperature"),
            },
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

        return payload

    def _prepare_text_data(self, call: dict) -> dict:
        title_prompt = self._get_title_prompt()
        return {
            "messages": [
                {"role": "user", "content": [{"text": title_prompt}]},
                {"role": "user", "content": [{"text": call.message}]},
            ],
            "inferenceConfig": {
                "maxTokens": call.max_tokens,
                "temperature": call.temperature,
            },
        }

    async def validate(self) -> None | ServiceValidationError:
        data = {
            "messages": [{"role": "user", "content": [{"text": "Hi"}]}],
            "inferenceConfig": {"maxTokens": 10, "temperature": 0.5},
        }
        await self.invoke_bedrock(model=self.model, data=data)


class ProviderFactory:
    """
    Factory to create provider instances from a provider name and config
    """

    @staticmethod
    def create(hass, provider_name: str, config: dict, model: str) -> Provider:
        if provider_name == "OpenAI":
            return OpenAI(
                hass=hass,
                api_key=config.get(CONF_API_KEY),
                model=model,
            )

        if provider_name == "Azure":
            return AzureOpenAI(
                hass,
                api_key=config.get(CONF_API_KEY),
                model=model,
                endpoint={
                    "base_url": ENDPOINT_AZURE,
                    "endpoint": config.get(CONF_AZURE_BASE_URL),
                    "deployment": config.get(CONF_AZURE_DEPLOYMENT),
                    "api_version": config.get(CONF_AZURE_VERSION),
                },
            )

        if provider_name == "Anthropic":
            return Anthropic(hass, api_key=config.get(CONF_API_KEY), model=model)

        if provider_name == "Google":
            return Google(
                hass,
                api_key=config.get(CONF_API_KEY),
                model=model,
                endpoint={"base_url": ENDPOINT_GOOGLE},
            )

        if provider_name == "Groq":
            return Groq(hass, api_key=config.get(CONF_API_KEY), model=model)

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
                api_key=config.get(CONF_API_KEY),
                model=model,
                endpoint={"base_url": config.get(CONF_CUSTOM_OPENAI_ENDPOINT)},
            )

        if provider_name == "AWS Bedrock":
            return AWSBedrock(
                hass,
                aws_access_key_id=config.get(CONF_AWS_ACCESS_KEY_ID),
                aws_secret_access_key=config.get(CONF_AWS_SECRET_ACCESS_KEY),
                aws_region_name=config.get(CONF_AWS_REGION_NAME),
                model=model,
            )

        if provider_name == "OpenWebUI":
            endpoint = ENDPOINT_OPENWEBUI.format(
                ip_address=config.get(CONF_IP_ADDRESS),
                port=config.get(CONF_PORT),
                protocol="https" if config.get(CONF_HTTPS, False) else "http",
            )
            return OpenAI(
                hass,
                api_key=config.get(CONF_API_KEY),
                model=model,
                endpoint={"base_url": endpoint},
            )

        if provider_name == "OpenRouter":
            return OpenAI(
                hass,
                api_key=config.get(CONF_API_KEY),
                model=model,
                endpoint={"base_url": ENDPOINT_OPENROUTER},
            )

        raise ServiceValidationError("invalid_provider")
