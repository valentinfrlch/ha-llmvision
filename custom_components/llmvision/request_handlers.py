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
    ENDPOINT_OPENAI,
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
}.get(provider, "gpt-4o-mini")  # Default value if provider is not found


class RequestHandler:
    """class to handle requests to AI providers"""

    def __init__(self, hass, message, max_tokens, temperature, detail):
        self.session = async_get_clientsession(hass)
        self.hass = hass
        self.message = message
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.detail = detail
        self.base64_images = []
        self.filenames = []

    async def make_request(self, call):
        """Forward request to providers"""
        entry_id = call.provider
        provider = get_provider(self.hass, entry_id)
        _LOGGER.info(f"Provider from call: {provider}")
        model = call.model if call.model != "None" else default_model(provider)

        if provider == 'OpenAI':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_OPENAI_API_KEY)
            self._validate_call(provider=provider,
                                api_key=api_key,
                                base64_images=self.base64_images)
            response_text = await self.openai(model=model, api_key=api_key)
        elif provider == 'Anthropic':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_ANTHROPIC_API_KEY)
            self._validate_call(provider=provider,
                                api_key=api_key,
                                base64_images=self.base64_images)
            response_text = await self.anthropic(model=model, api_key=api_key)
        elif provider == 'Google':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_GOOGLE_API_KEY)
            self._validate_call(provider=provider,
                                api_key=api_key,
                                base64_images=self.base64_images)
            response_text = await self.google(model=model, api_key=api_key)
        elif provider == 'Groq':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_GROQ_API_KEY)
            self._validate_call(provider=provider,
                                api_key=api_key,
                                base64_images=self.base64_images)
            response_text = await self.groq(model=model, api_key=api_key)
        elif provider == 'LocalAI':
            ip_address = self.hass.data.get(
                DOMAIN).get(
                entry_id).get(CONF_LOCALAI_IP_ADDRESS)
            port = self.hass.data.get(
                DOMAIN).get(
                entry_id).get(CONF_LOCALAI_PORT)
            https = self.hass.data.get(
                DOMAIN).get(
                entry_id).get(CONF_LOCALAI_HTTPS, False)
            self._validate_call(provider=provider,
                                api_key=None,
                                base64_images=self.base64_images,
                                ip_address=ip_address,
                                port=port)
            response_text = await self.localai(model=model,
                                               ip_address=ip_address,
                                               port=port,
                                               https=https)
        elif provider == 'Ollama':
            ip_address = self.hass.data.get(
                DOMAIN).get(
                entry_id).get(CONF_OLLAMA_IP_ADDRESS)
            port = self.hass.data.get(DOMAIN).get(
                entry_id).get(CONF_OLLAMA_PORT)
            https = self.hass.data.get(DOMAIN).get(
                entry_id).get(
                CONF_OLLAMA_HTTPS, False)
            self._validate_call(provider=provider,
                                api_key=None,
                                base64_images=self.base64_images,
                                ip_address=ip_address,
                                port=port)
            response_text = await self.ollama(model=model,
                                              ip_address=ip_address,
                                              port=port,
                                              https=https)
        elif provider == 'Custom OpenAI':
            api_key = self.hass.data.get(DOMAIN).get(
                entry_id).get(
                CONF_CUSTOM_OPENAI_API_KEY, "")
            endpoint = self.hass.data.get(DOMAIN).get(entry_id).get(
                CONF_CUSTOM_OPENAI_ENDPOINT) + "/v1/chat/completions"
            self._validate_call(provider=provider,
                                api_key=api_key,
                                base64_images=self.base64_images)
            response_text = await self.openai(model=model, api_key=api_key, endpoint=endpoint)
        else:
            raise ServiceValidationError("invalid_provider")
        return {"response_text": response_text}

    def add_frame(self, base64_image, filename):
        self.base64_images.append(base64_image)
        self.filenames.append(filename)

    # Request Handlers
    async def openai(self, model, api_key, endpoint=ENDPOINT_OPENAI):
        # Set headers and payload
        headers = {'Content-type': 'application/json',
                   'Authorization': 'Bearer ' + api_key}
        data = {"model": model,
                "messages": [{"role": "user", "content": [
                ]}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
                }

        # Add the images to the request
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" else filename
            data["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            data["messages"][0]["content"].append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}", "detail": self.detail}})

        # append the message to the end of the request
        data["messages"][0]["content"].append(
            {"type": "text", "text": self.message}
        )

        response = await self._post(
            url=endpoint, headers=headers, data=data)

        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    async def anthropic(self, model, api_key):
        # Set headers and payload
        headers = {'content-type': 'application/json',
                   'x-api-key': api_key,
                   'anthropic-version': VERSION_ANTHROPIC}
        data = {"model": model,
                "messages": [
                    {"role": "user", "content": []}
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
                }

        # Add the images to the request
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" or not filename else filename
            data["messages"][0]["content"].append(
                {
                    "type": "text",
                    "text": tag + ":"
                })
            data["messages"][0]["content"].append(
                {"type": "image", "source":
                    {"type": "base64",
                     "media_type": "image/jpeg",
                     "data": f"{image}"
                     }
                 }
            )

        # append the message to the end of the request
        data["messages"][0]["content"].append(
            {"type": "text", "text": self.message}
        )

        response = await self._post(
            url=ENDPOINT_ANTHROPIC, headers=headers, data=data)

        response_text = response.get("content")[0].get("text")
        return response_text

    async def google(self, model, api_key):
        # Set headers and payload
        headers = {'content-type': 'application/json'}
        data = {"contents": [
        ],
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                "temperature": self.temperature
        }
        }

        # Add the images to the request
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" or not filename else filename
            data["contents"].append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": tag + ":"
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image
                            }
                        }
                    ]
                }
            )

        # append the message to the end of the request
        data["contents"].append(
            {"role": "user",
             "parts": [{"text": self.message}
                       ]
             }
        )

        response = await self._post(
            url=ENDPOINT_GOOGLE.format(model=model, api_key=api_key), headers=headers, data=data)

        response_text = response.get("candidates")[0].get(
            "content").get("parts")[0].get("text")
        return response_text

    async def groq(self, model, api_key, endpoint=ENDPOINT_GROQ):
        first_image = self.base64_images[0]
        # Set headers and payload
        headers = {'Content-type': 'application/json',
                   'Authorization': 'Bearer ' + api_key}
        data = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.message},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{first_image}"}
                        }
                    ]
                }
            ],
            "model": model
        }

        response = await self._post(
            url=endpoint, headers=headers, data=data)

        print(response)

        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    async def localai(self, model, ip_address, port, https):
        data = {"model": model,
                "messages": [{"role": "user", "content": [
                ]}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
                }
        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" or not filename else filename
            data["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            data["messages"][0]["content"].append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})

        # append the message to the end of the request
        data["messages"][0]["content"].append(
            {"type": "text", "text": self.message}
        )

        protocol = "https" if https else "http"
        response = await self._post(
            url=ENDPOINT_LOCALAI.format(ip_address=ip_address, port=port, protocol=protocol), headers={}, data=data)

        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    async def ollama(self, model, ip_address, port, https):
        data = {
            "model": model,
            "messages": [],
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": self.temperature
            }
        }

        for image, filename in zip(self.base64_images, self.filenames):
            tag = ("Image " + str(self.base64_images.index(image) + 1)
                   ) if filename == "" or not filename else filename
            image_message = {
                "role": "user",
                "content": tag + ":",
                "images": [image]
            }
            data["messages"].append(image_message)
        # append to the end of the request
        prompt_message = {
            "role": "user",
            "content": self.message
        }
        data["messages"].append(prompt_message)

        protocol = "https" if https else "http"
        response = await self._post(url=ENDPOINT_OLLAMA.format(ip_address=ip_address, port=port, protocol=protocol), headers={}, data=data)
        response_text = response.get("message").get("content")
        return response_text

    # Helpers
    async def _post(self, url, headers, data):
        """Post data to url and return response data"""
        _LOGGER.info(f"Request data: {sanitize_data(data)}")

        try:
            response = await self.session.post(url, headers=headers, json=data)
        except Exception as e:
            raise ServiceValidationError(f"Request failed: {e}")

        if response.status != 200:
            provider = inspect.stack()[1].function
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
        return None

    def _validate_call(self, provider, api_key, base64_images, ip_address=None, port=None):
        """Validate the service call data"""
        # Checks for OpenAI
        if provider == 'OpenAI':
            if not api_key:
                raise ServiceValidationError(ERROR_OPENAI_NOT_CONFIGURED)
        # Checks for Anthropic
        elif provider == 'Anthropic':
            if not api_key:
                raise ServiceValidationError(ERROR_ANTHROPIC_NOT_CONFIGURED)
        elif provider == 'Google':
            if not api_key:
                raise ServiceValidationError(ERROR_GOOGLE_NOT_CONFIGURED)
        # Checks for Groq
        elif provider == 'Groq':
            if not api_key:
                raise ServiceValidationError(ERROR_GROQ_NOT_CONFIGURED)
            if len(base64_images) > 1:
                raise ServiceValidationError(ERROR_GROQ_MULTIPLE_IMAGES)
        # Checks for LocalAI
        elif provider == 'LocalAI':
            if not ip_address or not port:
                raise ServiceValidationError(ERROR_LOCALAI_NOT_CONFIGURED)
        # Checks for Ollama
        elif provider == 'Ollama':
            if not ip_address or not port:
                raise ServiceValidationError(ERROR_OLLAMA_NOT_CONFIGURED)
        elif provider == 'Custom OpenAI':
            pass
        else:
            raise ServiceValidationError(
                "Invalid provider selected. The event calendar cannot be used for analysis.")
        # Check media input
        if base64_images == []:
            raise ServiceValidationError(ERROR_NO_IMAGE_INPUT)

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
