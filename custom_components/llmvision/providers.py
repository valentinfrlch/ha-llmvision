from abc import ABC, abstractmethod
import openai
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import logging
import asyncio
import inspect
from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
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
    ENDPOINT_ANTHROPIC,
    ENDPOINT_GOOGLE,
    ENDPOINT_LOCALAI,
    ENDPOINT_OLLAMA,
    ENDPOINT_GROQ,
    ERROR_OPENAI_NOT_CONFIGURED,
    ERROR_ANTHROPIC_NOT_CONFIGURED,
    ERROR_GOOGLE_NOT_CONFIGURED,
    ERROR_GROQ_NOT_CONFIGURED,
    ERROR_GROQ_MULTIPLE_IMAGES,
    ERROR_LOCALAI_NOT_CONFIGURED,
    ERROR_OLLAMA_NOT_CONFIGURED,
    ERROR_NO_IMAGE_INPUT
)

_LOGGER = logging.getLogger(__name__)


def sanitize_data(data):
    """Remove long string data from request data to reduce log size"""
    if isinstance(data, dict):
        return {key: sanitize_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, str) and len(data) > 400 and data.count(' ') < 50:
        return '<long_string>'
    else:
        return data


def get_provider(hass, provider_uid):
    """Translate UID of the config entry into provider name"""
    if DOMAIN not in hass.data:
        return None

    entry_data = hass.data[DOMAIN].get(provider_uid)
    if not entry_data:
        return None

    if CONF_OPENAI_API_KEY in entry_data:
        return "OpenAI"
    elif CONF_ANTHROPIC_API_KEY in entry_data:
        return "Anthropic"
    elif CONF_GOOGLE_API_KEY in entry_data:
        return "Google"
    elif CONF_GROQ_API_KEY in entry_data:
        return "Groq"
    elif CONF_LOCALAI_IP_ADDRESS in entry_data:
        return "LocalAI"
    elif CONF_OLLAMA_IP_ADDRESS in entry_data:
        return "Ollama"
    elif CONF_CUSTOM_OPENAI_API_KEY in entry_data:
        return "Custom OpenAI"

    return None


def default_model(provider): return {
    "OpenAI": "gpt-4o-mini",
    "Anthropic": "claude-3-5-sonnet-latest",
    "Google": "gemini-1.5-flash-latest",
    "Groq": "llava-v1.5-7b-4096-preview",
    "LocalAI": "gpt-4-vision-preview",
    "Ollama": "llava-phi3:latest",
    "Custom OpenAI": "gpt-4o-mini"
}.get(provider, "gpt-4o-mini")  # Default value


class RequestHandler:
    def __init__(self, hass, message, max_tokens, temperature):
        self.session = async_get_clientsession(hass)
        self.hass = hass
        self.message = message
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.base64_images = []
        self.filenames = []

    async def forward_request(self, call):
        entry_id = call.provider
        provider = get_provider(self.hass, entry_id)
        _LOGGER.info(f"Provider from call: {provider}")
        model = call.model if call.model != "None" else default_model(provider)

        if provider == 'OpenAI':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_OPENAI_API_KEY)

            request = OpenAI(self.session, model, self.max_tokens, self.temperature,
                             self.message, self.base64_images, self.filenames)
            response_text = await request.vision_request(api_key=api_key)
        elif provider == 'Anthropic':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_ANTHROPIC_API_KEY)

            request = Anthropic(self.session, model, self.max_tokens, self.temperature,
                                self.message, self.base64_images, self.filenames)
            response_text = await request.vision_request(api_key=api_key, endpoint=ENDPOINT_ANTHROPIC)
        elif provider == 'Google':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_GOOGLE_API_KEY)

            request = Google(self.session, model, self.max_tokens, self.temperature,
                             self.message, self.base64_images, self.filenames)
            response_text = await request.vision_request(api_key=api_key, endpoint=ENDPOINT_GOOGLE)
        elif provider == 'Groq':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_GROQ_API_KEY)

            request = Groq(self.session, model, self.max_tokens, self.temperature,
                           self.message, self.base64_images, self.filenames)
            response_text = await request.vision_request(api_key=api_key, endpoint=ENDPOINT_GROQ)
        elif provider == 'LocalAI':
            ip_address = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_LOCALAI_IP_ADDRESS)
            port = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_LOCALAI_PORT)
            https = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_LOCALAI_HTTPS, False)

            request = LocalAI(self.session, model, self.max_tokens, self.temperature,
                              self.message, self.base64_images, self.filenames)
            response_text = await request.vision_request(endpoint=ENDPOINT_LOCALAI, ip_address=ip_address, port=port, https=https)
        elif provider == 'Ollama':
            ip_address = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_OLLAMA_IP_ADDRESS)
            port = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_OLLAMA_PORT)
            https = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_OLLAMA_HTTPS, False)
    
            request = Ollama(self.session, model, self.max_tokens, self.temperature,
                             self.message, self.base64_images, self.filenames)
            response_text = await request.vision_request(endpoint=ENDPOINT_OLLAMA, ip_address=ip_address, port=port, https=https)
        elif provider == 'Custom OpenAI':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_CUSTOM_OPENAI_API_KEY, "")
            endpoint = self.hass.data.get(DOMAIN).get(entry_id).get(
                CONF_CUSTOM_OPENAI_ENDPOINT) + "/v1/chat/completions"
      
            request = OpenAI(self.session, model, self.max_tokens, self.temperature,
                             self.message, self.base64_images, self.filenames)
            response_text = await request.vision_request(api_key, endpoint)
        else:
            raise ServiceValidationError("invalid_provider")
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
    def __init__(self, session, model, max_tokens, temperature, message, base64_images, filenames):
        self.session = session
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.message = message
        self.base64_images = base64_images
        self.filenames = filenames

    @abstractmethod
    async def _make_request(self, **kwargs) -> str:
        pass

    @abstractmethod
    def validate(self) -> bool:
        pass

    def validate_images(self):
        if not self.base64_images or len(self.base64_images) == 0:
            raise ServiceValidationError(ERROR_NO_IMAGE_INPUT)

    async def vision_request(self, **kwargs) -> str:
        self.validate_images()
        self.validate(**kwargs)
        kwargs["data"] = self._prepare_vision_data()
        _LOGGER.info(f"kwargs: {kwargs.items()}")
        return await self._make_request(**kwargs)

    async def text_request(self, **kwargs) -> str:
        self.validate_images()
        self.validate(**kwargs)
        kwargs["data"] = self._prepare_text_data()
        return await self._make_request(**kwargs)

    async def _post(self, url, headers, data) -> dict:
        """Post data to url and return response data"""
        _LOGGER.info(f"Request data: {sanitize_data(data)}")

        try:
            _LOGGER.info(f"Posting to {url} with headers {headers}")
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

    async def _fetch(self, url, max_retries=2, retry_delay=1):
        """Fetch image from url and return image data"""
        retries = 0
        while retries < max_retries:
            _LOGGER.info(
                f"Fetching {url} (attempt {retries + 1}/{max_retries})")
            try:
                response = await self.session.get(url)
                if response.status != 200:
                    _LOGGER.warning(
                        f"Couldn't fetch frame (status code: {response.status})")
                    retries += 1
                    await asyncio.sleep(retry_delay)
                    continue
                data = await response.read()
                return data
            except Exception as e:
                _LOGGER.error(f"Fetch failed: {e}")
                retries += 1
                await asyncio.sleep(retry_delay)
        _LOGGER.warning(f"Failed to fetch {url} after {max_retries} retries")
    
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
    def __init__(self, session, model, max_tokens, temperature, message, base64_images, filenames):
        super().__init__(session, model, max_tokens, temperature,
                         message, base64_images, filenames)

    async def _make_request(self, **kwargs) -> str:
        openai.api_key = kwargs.get("api_key")
        messages = kwargs.get("data")
        if "endpoint" in kwargs:
            openai.base_url = kwargs.get("endpoint")

        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        response_text = response.choices[0].message.content
        return response_text

    def _prepare_vision_data(self) -> list:
        messages = [{"role": "user", "content": []}]
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            messages[0]["content"].append({"type": "text", "text": tag + ":"})
            messages[0]["content"].append({"type": "image_url", "image_url": {
                                          "url": f"data:image/jpeg;base64,{image}"}})
        messages[0]["content"].append({"type": "text", "text": self.message})
        return messages

    def _prepare_text_data(self) -> list:
        return [{"role": "user", "content": [{"type": "text", "text": self.message}]}]
    
    def validate(self, **kwargs):
        if not kwargs.get("api_key"):
            raise ServiceValidationError(ERROR_OPENAI_NOT_CONFIGURED)
        

class Anthropic(Provider):
    def __init__(self, session, model, max_tokens, temperature, message, base64_images, filenames):
        super().__init__(session, model, max_tokens, temperature,
                         message, base64_images, filenames)

    def _generate_headers(self, api_key: str) -> dict:
        return {
            'content-type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': VERSION_ANTHROPIC
        }

    async def _make_request(self, **kwargs) -> str:
        api_key = kwargs.get("api_key")
        endpoint = kwargs.get("endpoint")
        data = kwargs.get("data")

        headers = self._generate_headers(api_key)
        response = await self._post(url=endpoint, headers=headers, data=data)
        response_text = response.get("content")[0].get("text")
        return response_text

    def _prepare_vision_data(self) -> dict:
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": []}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            data["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            data["messages"][0]["content"].append({"type": "image", "source": {
                                                  "type": "base64", "media_type": "image/jpeg", "data": f"{image}"}})
        data["messages"][0]["content"].append(
            {"type": "text", "text": self.message})
        return data

    def _prepare_text_data(self) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": [{"type": "text", "text": self.message}]}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

    def validate(self, **kwargs):
        if not kwargs.get("api_key"):
            raise ServiceValidationError(ERROR_ANTHROPIC_NOT_CONFIGURED)


class Google(Provider):
    def __init__(self, session, model, max_tokens, temperature, message, base64_images, filenames):
        super().__init__(session, model, max_tokens, temperature,
                         message, base64_images, filenames)

    def _generate_headers(self) -> dict:
        return {'content-type': 'application/json'}

    async def _make_request(self, **kwargs) -> str:
        api_key = kwargs.get("api_key")
        endpoint = kwargs.get("endpoint")
        data = kwargs.get("data")

        headers = self._generate_headers()
        response = await self._post(url=endpoint.format(model=self.model, api_key=api_key), headers=headers, data=data)
        response_text = response.get("candidates")[0].get(
            "content").get("parts")[0].get("text")
        return response_text

    def _prepare_vision_data(self) -> dict:
        data = {"contents": [], "generationConfig": {
            "maxOutputTokens": self.max_tokens, "temperature": self.temperature}}
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            data["contents"].append({"role": "user", "parts": [
                                    {"text": tag + ":"}, {"inline_data": {"mime_type": "image/jpeg", "data": image}}]})
        data["contents"].append(
            {"role": "user", "parts": [{"text": self.message}]})
        return data

    def _prepare_text_data(self) -> dict:
        return {
            "contents": [{"role": "user", "parts": [{"text": self.message + ":"}]}],
            "generationConfig": {"maxOutputTokens": self.max_tokens, "temperature": self.temperature}
        }
    
    def validate(self, **kwargs):
        if not kwargs.get("api_key"):
            raise ServiceValidationError(ERROR_GOOGLE_NOT_CONFIGURED)


class Groq(Provider):
    def __init__(self, session, model, max_tokens, temperature, message, base64_images, filenames):
        super().__init__(session, model, max_tokens, temperature,
                         message, base64_images, filenames)

    def _generate_headers(self, api_key: str) -> dict:
        return {'Content-type': 'application/json', 'Authorization': 'Bearer ' + api_key}

    async def _make_request(self, **kwargs) -> str:
        api_key = kwargs.get("api_key")
        endpoint = kwargs.get("endpoint")
        data = kwargs.get("data")

        headers = self._generate_headers(api_key)
        response = await self._post(url=endpoint, headers=headers, data=data)
        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self) -> dict:
        first_image = self.base64_images[0]
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.message},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{first_image}"}}
                    ]
                }
            ],
            "model": self.model
        }
        return data

    def _prepare_text_data(self) -> dict:
        return {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.message}
                    ]
                }
            ],
            "model": self.model
        }
    
    def validate(self, **kwargs):
        if not kwargs.get("api_key"):
            raise ServiceValidationError(ERROR_GROQ_NOT_CONFIGURED)
        if len(kwargs.get("base64_images")) > 1:
            raise ServiceValidationError(ERROR_GROQ_MULTIPLE_IMAGES)


class LocalAI(Provider):
    def __init__(self, session, model, max_tokens, temperature, message, base64_images, filenames):
        super().__init__(session, model, max_tokens, temperature,
                         message, base64_images, filenames)

    async def _make_request(self, **kwargs) -> str:
        endpoint = kwargs.get("endpoint")
        data = kwargs.get("data")
        https = kwargs.get("https")
        ip_address = kwargs.get("ip_address")
        port = kwargs.get("port")

        headers = self._generate_headers()
        protocol = "https" if https else "http"
        response = await self._post(url=endpoint.format(ip_address=ip_address, port=port, protocol=protocol), headers=headers, data=data)
        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    def _prepare_vision_data(self) -> dict:
        data = {"model": self.model, "messages": [{"role": "user", "content": [
        ]}], "max_tokens": self.max_tokens, "temperature": self.temperature}
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            data["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            data["messages"][0]["content"].append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})
        data["messages"][0]["content"].append(
            {"type": "text", "text": self.message})
        return data

    def _prepare_text_data(self) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": [{"type": "text", "text": self.message}]}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
    
    def validate(self, **kwargs):
        if not kwargs.get("ip_address") or not kwargs.get("port"):
            raise ServiceValidationError(ERROR_LOCALAI_NOT_CONFIGURED)


class Ollama(Provider):
    def __init__(self, session, model, max_tokens, temperature, message, base64_images, filenames):
        super().__init__(session, model, max_tokens, temperature,
                         message, base64_images, filenames)

    async def _make_request(self, **kwargs) -> str:
        endpoint = kwargs.get("endpoint")
        data = kwargs.get("data")
        https = kwargs.get("https")
        ip_address = kwargs.get("ip_address")
        port = kwargs.get("port")

        _LOGGER.info(f"endpoint: {endpoint} https: {https} ip_address: {ip_address} port: {port}")

        headers = {}
        protocol = "https" if https else "http"
        response = await self._post(url=endpoint.format(ip_address=ip_address, port=port, protocol=protocol), headers=headers, data=data)
        response_text = response.get("message").get("content")
        return response_text

    def _prepare_vision_data(self) -> dict:
        data = {"model": self.model, "messages": [], "stream": False, "options": {
            "num_predict": self.max_tokens, "temperature": self.temperature}}
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            image_message = {"role": "user",
                             "content": tag + ":", "images": [image]}
            data["messages"].append(image_message)
        prompt_message = {"role": "user", "content": self.message}
        data["messages"].append(prompt_message)
        return data

    def _prepare_text_data(self) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": self.message}],
            "stream": False,
            "options": {"num_predict": self.max_tokens, "temperature": self.temperature}
        }

    def validate(self, **kwargs):
        if not kwargs.get("ip_address") or not kwargs.get("port"):
            raise ServiceValidationError(ERROR_OLLAMA_NOT_CONFIGURED)