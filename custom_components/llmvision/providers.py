from abc import ABC, abstractmethod
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import logging
import inspect
import re
from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
    CONF_AZURE_API_KEY,
    CONF_AZURE_BASE_URL,
    CONF_AZURE_DEPLOYMENT,
    CONF_AZURE_VERSION,
    CONF_ANTHROPIC_API_KEY,
    CONF_GOOGLE_API_KEY,
    CONF_GROQ_API_KEY,
    CONF_LOCALAI_IP_ADDRESS,
    CONF_LOCALAI_PORT,
    CONF_LOCALAI_HTTPS,
    CONF_OLLAMA_IP_ADDRESS,
    CONF_OLLAMA_PORT,
    CONF_OLLAMA_HTTPS,
    CONF_CUSTOM_OPENAI_ENDPOINT,
    CONF_CUSTOM_OPENAI_API_KEY,
    VERSION_ANTHROPIC,
    ENDPOINT_OPENAI,
    ENDPOINT_AZURE,
    ENDPOINT_ANTHROPIC,
    ENDPOINT_GOOGLE,
    ENDPOINT_LOCALAI,
    ENDPOINT_OLLAMA,
    ENDPOINT_GROQ,
    ERROR_NOT_CONFIGURED,
    ERROR_GROQ_MULTIPLE_IMAGES,
    ERROR_NO_IMAGE_INPUT,
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
        elif isinstance(data, str) and len(data) > 400 and data.count(' ') < 50:
            return '<long_string>'
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

        if CONF_ANTHROPIC_API_KEY in entry_data:
            return "Anthropic"
        elif CONF_AZURE_API_KEY in entry_data:
            return "Azure"
        elif CONF_CUSTOM_OPENAI_API_KEY in entry_data:
            return "Custom OpenAI"
        elif CONF_GOOGLE_API_KEY in entry_data:
            return "Google"
        elif CONF_GROQ_API_KEY in entry_data:
            return "Groq"
        elif CONF_LOCALAI_IP_ADDRESS in entry_data:
            return "LocalAI"
        elif CONF_OLLAMA_IP_ADDRESS in entry_data:
            return "Ollama"
        elif CONF_OPENAI_API_KEY in entry_data:
            return "OpenAI"

        return None

    def validate(self, call) -> None | ServiceValidationError:
        """Validate call data"""
        # Check image input
        if not call.base64_images:
            raise ServiceValidationError(ERROR_NO_IMAGE_INPUT)
        # Check if single image is provided for Groq
        if len(call.base64_images) > 1 and self.get_provider(self.hass, call.provider) == 'Groq':
            raise ServiceValidationError(ERROR_GROQ_MULTIPLE_IMAGES)
        # Check provider is configured
        if not call.provider:
            raise ServiceValidationError(ERROR_NOT_CONFIGURED)

    async def call(self, call):
        """
        Forwards a request to the specified provider and optionally generates a title.

        Args:
            call (object): The call object containing request details.

        Raises:
            ServiceValidationError: If the provider is invalid.

        Returns:
            dict: A dictionary containing the generated title (if any) and the response text.
        """
        entry_id = call.provider
        config = self.hass.data.get(DOMAIN).get(entry_id)

        provider = Request.get_provider(self.hass, entry_id)
        call.base64_images = self.base64_images
        call.filenames = self.filenames

        self.validate(call)

        gen_title_prompt = "Your job is to generate a title in the form '<object> seen' for texts. Do not mention the time, do not speculate. Generate a title for this text: {response}"

        if provider == 'OpenAI':
            api_key = config.get(CONF_OPENAI_API_KEY)
            provider_instance = OpenAI(hass=self.hass, api_key=api_key)

        elif provider == 'Azure':
            api_key = config.get(CONF_AZURE_API_KEY)
            endpoint = config.get(CONF_AZURE_BASE_URL)
            deployment = config.get(CONF_AZURE_DEPLOYMENT)
            version = config.get(CONF_AZURE_VERSION)

            provider_instance = AzureOpenAI(self.hass,
                                            api_key=api_key,
                                            endpoint={
                                                'base_url': ENDPOINT_AZURE,
                                                'endpoint': endpoint,
                                                'deployment': deployment,
                                                'api_version': version
                                            })

        elif provider == 'Anthropic':
            api_key = config.get(CONF_ANTHROPIC_API_KEY)
            provider_instance = Anthropic(self.hass, api_key=api_key)

        elif provider == 'Google':
            api_key = config.get(CONF_GOOGLE_API_KEY)
            model = call.model if call.model and call.model != "None" else "gemini-1.5-flash-latest"
            provider_instance = Google(self.hass, api_key=api_key, endpoint={'base_url': ENDPOINT_GOOGLE, 'model': model})

        elif provider == 'Groq':
            api_key = config.get(CONF_GROQ_API_KEY)
            provider_instance = Groq(self.hass, api_key=api_key)

        elif provider == 'LocalAI':
            ip_address = config.get(CONF_LOCALAI_IP_ADDRESS)
            port = config.get(CONF_LOCALAI_PORT)
            https = config.get(CONF_LOCALAI_HTTPS, False)

            provider_instance = LocalAI(self.hass, endpoint={
                'ip_address': ip_address,
                'port': port,
                'https': https
            })

        elif provider == 'Ollama':
            ip_address = config.get(CONF_OLLAMA_IP_ADDRESS)
            port = config.get(CONF_OLLAMA_PORT)
            https = config.get(CONF_OLLAMA_HTTPS, False)

            provider_instance = Ollama(self.hass, endpoint={
                'ip_address': ip_address,
                'port': port,
                'https': https
            })
            response_text = await provider_instance.vision_request(call)
            if call.generate_title:
                call.message = gen_title_prompt.format(response=response_text)
                gen_title = await provider_instance.title_request(call)

        elif provider == 'Custom OpenAI':
            api_key = config.get(CONF_CUSTOM_OPENAI_API_KEY, "")
            endpoint = config.get(
                CONF_CUSTOM_OPENAI_ENDPOINT) + "/v1/chat/completions"
            provider_instance = OpenAI(
                self.hass, api_key=api_key, endpoint=endpoint)

        else:
            raise ServiceValidationError("invalid_provider")

        # Make call to provider
        call.model = call.model if call.model and call.model != 'None' else provider_instance.default_model
        response_text = await provider_instance.vision_request(call)

        if call.generate_title:
            call.message = gen_title_prompt.format(response=response_text)
            gen_title = await provider_instance.title_request(call)

            return {"title": re.sub(r'[^a-zA-Z0-9\s]', '', gen_title), "response_text": response_text}
        else:
            return {"response_text": response_text}

    def add_frame(self, base64_image, filename):
        self.base64_images.append(base64_image)
        self.filenames.append(filename)

    async def _resolve_error(self, response, provider):
        """Translate response status to error message"""
        import json
        full_response_text = await response.text()
        _LOGGER.info(f"[INFO] Full Response: {full_response_text}")

        try:
            response_json = json.loads(full_response_text)
            if provider == 'anthropic':
                error_info = response_json.get('error', {})
                error_message = f"{error_info.get('type', 'Unknown error')}: {error_info.get('message', 'Unknown error')}"
            elif provider == 'ollama':
                error_message = response_json.get('error', 'Unknown error')
            else:
                error_info = response_json.get('error', {})
                error_message = error_info.get('message', 'Unknown error')
        except json.JSONDecodeError:
            error_message = 'Unknown error'

        return error_message


class Provider(ABC):
    """
    Abstract base class for providers

    Args:
        hass (object): Home Assistant instance
        api_key (str, optional): API key for the provider, defaults to ""
        endpoint (dict, optional): Endpoint configuration for the provider
    """

    def __init__(self,
                 hass,
                 api_key="",
                 endpoint={
                     'base_url': "",
                     'deployment': "",
                     'api_version': "",
                     'ip_address': "",
                     'port': "",
                     'https': False
                 }
                 ):
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.api_key = api_key
        self.endpoint = endpoint

    @abstractmethod
    async def _make_request(self, data) -> str:
        pass

    @abstractmethod
    def _prepare_vision_data(self, call) -> dict:
        pass

    @abstractmethod
    def _prepare_text_data(self, call) -> dict:
        pass

    @abstractmethod
    async def validate(self) -> None | ServiceValidationError:
        pass

    async def vision_request(self, call) -> str:
        data = self._prepare_vision_data(call)
        return await self._make_request(data)

    async def title_request(self, call) -> str:
        call.temperature = 0.1
        call.max_tokens = 5
        data = self._prepare_text_data(call)
        return await self._make_request(data)

    async def _post(self, url, headers, data) -> dict:
        """Post data to url and return response data"""
        _LOGGER.info(f"Request data: {Request.sanitize_data(data)}")

        try:
            _LOGGER.info(f"Posting to {url}")
            response = await self.session.post(url, headers=headers, json=data)
        except Exception as e:
            raise ServiceValidationError(f"Request failed: {e}")

        if response.status != 200:
            frame = inspect.stack()[1]
            provider = frame.frame.f_locals["self"].__class__.__name__.lower()
            parsed_response = await self._resolve_error(response, provider)
            raise ServiceValidationError(parsed_response)
        else:
            response_data = await response.json()
            _LOGGER.info(f"Response data: {response_data}")
            return response_data

    async def _resolve_error(self, response, provider) -> str:
        """Translate response status to error message"""
        import json
        full_response_text = await response.text()
        _LOGGER.info(f"[INFO] Full Response: {full_response_text}")

        try:
            response_json = json.loads(full_response_text)
            if provider == 'anthropic':
                error_info = response_json.get('error', {})
                error_message = f"{error_info.get('type', 'Unknown error')}: {error_info.get('message', 'Unknown error')}"
            elif provider == 'ollama':
                error_message = response_json.get('error', 'Unknown error')
            else:
                error_info = response_json.get('error', {})
                error_message = error_info.get('message', 'Unknown error')
        except json.JSONDecodeError:
            error_message = 'Unknown error'

        return error_message


class OpenAI(Provider):
    def __init__(self, hass, api_key="", endpoint={'base_url': ENDPOINT_OPENAI}):
        super().__init__(hass, api_key, endpoint=endpoint)
        self.default_model = "gpt-4o-mini"

    def _generate_headers(self) -> dict:
        return {'Content-type': 'application/json',
                'Authorization': 'Bearer ' + self.api_key}

    async def _make_request(self, data) -> str:
        headers = self._generate_headers()
        response = await self._post(url=self.endpoint.get('base_url'), headers=headers, data=data)
        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call) -> list:
        payload = {"model": call.model,
                   "messages": [{"role": "user", "content": []}],
                   "max_tokens": call.max_tokens,
                   "temperature": call.temperature
                   }

        for image, filename in zip(call.base64_images, call.filenames):
            tag = ("Image " + str(call.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            payload["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            payload["messages"][0]["content"].append({"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{image}"}})
        payload["messages"][0]["content"].append(
            {"type": "text", "text": call.message})
        return payload

    def _prepare_text_data(self, call) -> list:
        return {
            "model": call.model,
            "messages": [{"role": "user", "content": [{"type": "text", "text": call.message}]}],
            "max_tokens": call.max_tokens,
            "temperature": call.temperature
        }

    async def validate(self) -> None | ServiceValidationError:
        if self.api_key:
            headers = self._generate_headers()
            data = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
                "max_tokens": 1,
                "temperature": 0.5
            }
            await self._post(url=self.endpoint.get('base_url'), headers=headers, data=data)
        else:
            raise ServiceValidationError("empty_api_key")


class AzureOpenAI(Provider):
    def __init__(self, hass, api_key="", endpoint={'base_url': ENDPOINT_AZURE, 'endpoint': "", 'deployment': "", 'api_version': ""}):
        super().__init__(hass, api_key, endpoint)
        self.default_model = "gpt-4o-mini"

    def _generate_headers(self) -> dict:
        return {'Content-type': 'application/json',
                'api-key': self.api_key}

    async def _make_request(self, data) -> str:
        headers = self._generate_headers()
        endpoint = self.endpoint.get("base_url").format(
            base_url=self.endpoint.get("endpoint"),
            deployment=self.endpoint.get("deployment"),
            api_version=self.endpoint.get("api_version")
        )

        response = await self._post(url=endpoint, headers=headers, data=data)
        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call) -> list:
        payload = {"messages": [{"role": "user", "content": []}],
                   "max_tokens": call.max_tokens,
                   "temperature": call.temperature,
                   "stream": False
                   }
        for image, filename in zip(call.base64_images, call.filenames):
            tag = ("Image " + str(call.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            payload["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            payload["messages"][0]["content"].append({"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{image}"}})
        payload["messages"][0]["content"].append(
            {"type": "text", "text": call.message})
        return payload

    def _prepare_text_data(self, call) -> list:
        return {"messages": [{"role": "user", "content": [{"type": "text", "text": call.message}]}],
                "max_tokens": call.max_tokens,
                "temperature": call.temperature,
                "stream": False
                }

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")

        endpoint = self.endpoint.get("base_url").format(
            base_url=self.endpoint.get("endpoint"),
            deployment=self.endpoint.get("deployment"),
            api_version=self.endpoint.get("api_version")
        )
        headers = self._generate_headers()
        data = {"messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
                "max_tokens": 1,
                "temperature": 0.5,
                "stream": False
                }
        await self._post(url=endpoint, headers=headers, data=data)


class Anthropic(Provider):
    def __init__(self, hass, api_key=""):
        super().__init__(hass, api_key)
        self.default_model = "claude-3-5-sonnet-latest"

    def _generate_headers(self) -> dict:
        return {
            'content-type': 'application/json',
            'x-api-key': self.api_key,
            'anthropic-version': VERSION_ANTHROPIC
        }

    async def _make_request(self, data) -> str:
        headers = self._generate_headers()
        response = await self._post(url=ENDPOINT_ANTHROPIC, headers=headers, data=data)
        response_text = response.get("content")[0].get("text")
        return response_text

    def _prepare_vision_data(self, call) -> dict:
        data = {
            "model": call.model,
            "messages": [{"role": "user", "content": []}],
            "max_tokens": call.max_tokens,
            "temperature": call.temperature
        }
        for image, filename in zip(call.base64_images, call.filenames):
            tag = ("Image " + str(call.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            data["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            data["messages"][0]["content"].append({"type": "image", "source": {
                                                  "type": "base64", "media_type": "image/jpeg", "data": f"{image}"}})
        data["messages"][0]["content"].append(
            {"type": "text", "text": call.message})
        return data

    def _prepare_text_data(self, call) -> dict:
        return {
            "model": call.model,
            "messages": [{"role": "user", "content": [{"type": "text", "text": call.message}]}],
            "max_tokens": call.max_tokens,
            "temperature": call.temperature
        }

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")

        header = self._generate_headers()
        payload = {
            "model": "claude-3-haiku-20240307",
            "messages": [
                  {"role": "user", "content": "Hi"}
            ],
            "max_tokens": 1,
            "temperature": 0.5
        }
        await self._post(url=f"https://api.anthropic.com/v1/messages", headers=header, data=payload)


class Google(Provider):
    def __init__(self, hass, api_key="", endpoint={'base_url': ENDPOINT_GOOGLE, 'model': "gemini-1.5-flash-latest"}):
        super().__init__(hass, api_key, endpoint)
        self.default_model = "gemini-1.5-flash-latest"

    def _generate_headers(self) -> dict:
        return {'content-type': 'application/json'}

    async def _make_request(self, data) -> str:
        endpoint = self.endpoint.get('base_url').format(
            model=self.endpoint.get('model'), api_key=self.api_key)

        headers = self._generate_headers()
        response = await self._post(url=endpoint, headers=headers, data=data)
        response_text = response.get("candidates")[0].get(
            "content").get("parts")[0].get("text")
        return response_text

    def _prepare_vision_data(self, call) -> dict:
        data = {"contents": [], "generationConfig": {
            "maxOutputTokens": call.max_tokens, "temperature": call.temperature}}
        for image, filename in zip(call.base64_images, call.filenames):
            tag = ("Image " + str(call.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            data["contents"].append({"role": "user", "parts": [
                                    {"text": tag + ":"}, {"inline_data": {"mime_type": "image/jpeg", "data": image}}]})
        data["contents"].append(
            {"role": "user", "parts": [{"text": call.message}]})
        return data

    def _prepare_text_data(self, call) -> dict:
        return {
            "contents": [{"role": "user", "parts": [{"text": call.message + ":"}]}],
            "generationConfig": {"maxOutputTokens": call.max_tokens, "temperature": call.temperature}
        }

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")

        headers = self._generate_headers()
        data = {
            "contents": [{"role": "user", "parts": [{"text": "Hi"}]}],
            "generationConfig": {"maxOutputTokens": 1, "temperature": 0.5}
        }
        await self._post(url=self.endpoint.get('base_url').format(model=self.endpoint.get('model'), api_key=self.api_key), headers=headers, data=data)


class Groq(Provider):
    def __init__(self, hass, api_key=""):
        super().__init__(hass, api_key)
        self.default_model = "llama-3.2-11b-vision-preview"

    def _generate_headers(self) -> dict:
        return {'Content-type': 'application/json', 'Authorization': 'Bearer ' + self.api_key}

    async def _make_request(self, data) -> str:
        headers = self._generate_headers()
        response = await self._post(url=ENDPOINT_GROQ, headers=headers, data=data)
        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call) -> dict:
        first_image = call.base64_images[0]
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": call.message},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{first_image}"}}
                    ]
                }
            ],
            "model": call.model
        }
        return data

    def _prepare_text_data(self, call) -> dict:
        return {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": call.message}
                    ]
                }
            ],
            "model": call.model
        }

    async def validate(self) -> None | ServiceValidationError:
        if not self.api_key:
            raise ServiceValidationError("empty_api_key")
        headers = self._generate_headers()
        data = {
            "model": "llama3-8b-8192",
            "messages": [{
                "role": "user",
                "content": "Hi"
            }]
        }
        await self._post(url=ENDPOINT_GROQ, headers=headers, data=data)


class LocalAI(Provider):
    def __init__(self, hass, api_key="", endpoint={'ip_address': "", 'port': "", 'https': False}):
        super().__init__(hass, api_key, endpoint)
        self.default_model = "gpt-4-vision-preview"

    async def _make_request(self, data) -> str:
        endpoint = ENDPOINT_LOCALAI.format(
            protocol="https" if self.endpoint.get("https") else "http",
            ip_address=self.endpoint.get("ip_address"),
            port=self.endpoint.get("port")
        )

        headers = {}
        response = await self._post(url=endpoint, headers=headers, data=data)
        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call) -> dict:
        data = {"model": call.model, "messages": [{"role": "user", "content": [
        ]}], "max_tokens": call.max_tokens, "temperature": call.temperature}
        for image, filename in zip(call.base64_images, call.filenames):
            tag = ("Image " + str(call.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            data["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            data["messages"][0]["content"].append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})
        data["messages"][0]["content"].append(
            {"type": "text", "text": call.message})
        return data

    def _prepare_text_data(self, call) -> dict:
        return {
            "model": call.model,
            "messages": [{"role": "user", "content": [{"type": "text", "text": call.message}]}],
            "max_tokens": call.max_tokens,
            "temperature": call.temperature
        }

    async def validate(self) -> None | ServiceValidationError:
        if not self.endpoint.get("ip_address") or not self.endpoint.get("port"):
            raise ServiceValidationError('handshake_failed')
        session = async_get_clientsession(self.hass)
        ip_address = self.endpoint.get("ip_address")
        port = self.endpoint.get("port")
        protocol = "https" if self.endpoint.get("https") else "http"

        try:
            response = await session.get(f"{protocol}://{ip_address}:{port}/readyz")
            if response.status != 200:
                raise ServiceValidationError('handshake_failed')
        except Exception:
            raise ServiceValidationError('handshake_failed')


class Ollama(Provider):
    def __init__(self, hass, api_key="", endpoint={'ip_address': "0.0.0.0", 'port': "11434", 'https': False}):
        super().__init__(hass, api_key, endpoint)
        self.default_model = "minicpm-v"

    async def _make_request(self, data) -> str:
        https = self.endpoint.get("https")
        ip_address = self.endpoint.get("ip_address")
        port = self.endpoint.get("port")
        protocol = "https" if https else "http"
        endpoint = ENDPOINT_OLLAMA.format(
            ip_address=ip_address,
            port=port,
            protocol=protocol
        )

        response = await self._post(url=endpoint, headers={}, data=data)
        response_text = response.get("message").get("content")
        return response_text

    def _prepare_vision_data(self, call) -> dict:
        data = {"model": call.model, "messages": [], "stream": False, "options": {
            "num_predict": call.max_tokens, "temperature": call.temperature}}
        for image, filename in zip(call.base64_images, call.filenames):
            tag = ("Image " + str(call.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            image_message = {"role": "user",
                             "content": tag + ":", "images": [image]}
            data["messages"].append(image_message)
        prompt_message = {"role": "user", "content": call.message}
        data["messages"].append(prompt_message)
        return data

    def _prepare_text_data(self, call) -> dict:
        return {
            "model": call.model,
            "messages": [{"role": "user", "content": call.message}],
            "stream": False,
            "options": {"num_predict": call.max_tokens, "temperature": call.temperature}
        }

    async def validate(self) -> None | ServiceValidationError:
        if not self.endpoint.get("ip_address") or not self.endpoint.get("port"):
            raise ServiceValidationError('handshake_failed')
        session = async_get_clientsession(self.hass)
        ip_address = self.endpoint.get("ip_address")
        port = self.endpoint.get("port")
        protocol = "https" if self.endpoint.get("https") else "http"

        try:
            _LOGGER.info(
                f"Checking connection to {protocol}://{ip_address}:{port}")
            response = await session.get(f"{protocol}://{ip_address}:{port}/api/tags", headers={})
            _LOGGER.info(f"Response: {response}")
            if response.status != 200:
                raise ServiceValidationError('handshake_failed')
        except Exception as e:
            _LOGGER.error(f"Error: {e}")
            raise ServiceValidationError('handshake_failed')
