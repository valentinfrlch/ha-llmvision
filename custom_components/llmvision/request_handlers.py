from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import logging
import inspect
from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
    CONF_ANTHROPIC_API_KEY,
    CONF_GOOGLE_API_KEY,
    CONF_LOCALAI_IP_ADDRESS,
    CONF_LOCALAI_PORT,
    CONF_LOCALAI_HTTPS,
    CONF_OLLAMA_IP_ADDRESS,
    CONF_OLLAMA_PORT,
    CONF_OLLAMA_HTTPS,
    VERSION_ANTHROPIC,
    ENDPOINT_OPENAI,
    ENDPOINT_ANTHROPIC,
    ENDPOINT_GOOGLE,
    ENDPOINT_LOCALAI,
    ENDPOINT_OLLAMA,
    ERROR_OPENAI_NOT_CONFIGURED,
    ERROR_ANTHROPIC_NOT_CONFIGURED,
    ERROR_GOOGLE_NOT_CONFIGURED,
    ERROR_LOCALAI_NOT_CONFIGURED,
    ERROR_OLLAMA_NOT_CONFIGURED,
    ERROR_NO_IMAGE_INPUT
)

_LOGGER = logging.getLogger(__name__)
# base64_pattern = re.compile(r'([A-Za-z0-9+/=]{1000,})')


def sanitize_data(data):
    """Remove long string data from request data to reduce log size"""
    if isinstance(data, dict):
        return {key: sanitize_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, str) and len(data) > 200:
        return '<long_string>'
    else:
        return data


class RequestHandler:
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
        _LOGGER.debug(f"Base64 Images: {sanitize_data(self.base64_images)}")
        if call.provider == 'OpenAI':
            api_key = self.hass.data.get(DOMAIN).get(CONF_OPENAI_API_KEY)
            model = call.model
            self._validate_call(provider=call.provider,
                                api_key=api_key,
                                base64_images=self.base64_images)
            response_text = await self.openai(model=model, api_key=api_key)
        elif call.provider == 'Anthropic':
            api_key = self.hass.data.get(DOMAIN).get(CONF_ANTHROPIC_API_KEY)
            model = call.model
            self._validate_call(provider=call.provider,
                                api_key=api_key,
                                base64_images=self.base64_images)
            response_text = await self.anthropic(model=model, api_key=api_key)
        elif call.provider == 'Google':
            api_key = self.hass.data.get(DOMAIN).get(CONF_GOOGLE_API_KEY)
            model = call.model
            self._validate_call(provider=call.provider,
                                api_key=api_key,
                                base64_images=self.base64_images)
            response_text = await self.google(model=model, api_key=api_key)
        elif call.provider == 'LocalAI':
            ip_address = self.hass.data.get(
                DOMAIN, {}).get(CONF_LOCALAI_IP_ADDRESS)
            port = self.hass.data.get(
                DOMAIN, {}).get(CONF_LOCALAI_PORT)
            https = self.hass.data.get(
                DOMAIN, {}).get(CONF_LOCALAI_HTTPS, False)
            model = call.model
            self._validate_call(provider=call.provider,
                                api_key=None,
                                base64_images=self.base64_images,
                                ip_address=ip_address,
                                port=port)
            response_text = await self.localai(model=model,
                                               ip_address=ip_address,
                                               port=port,
                                               https=https)
        elif call.provider == 'Ollama':
            ip_address = self.hass.data.get(DOMAIN, {}).get(CONF_OLLAMA_IP_ADDRESS)
            port = self.hass.data.get(DOMAIN, {}).get(CONF_OLLAMA_PORT)
            https = self.hass.data.get(DOMAIN, {}).get(CONF_OLLAMA_HTTPS, False)
            model = call.model
            self._validate_call(provider=call.provider,
                                api_key=None,
                                base64_images=self.base64_images,
                                ip_address=ip_address,
                                port=port)
            response_text = await self.ollama(model=model,
                                              ip_address=ip_address,
                                              port=port,
                                              https=https)

        return {"response_text": response_text}

    def add_frame(self, base64_image, filename):
        self.base64_images.append(base64_image)
        self.filenames.append(filename)

    # Request Handlers
    async def openai(self, model, api_key):
        from .const import ENDPOINT_OPENAI
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
            url=ENDPOINT_OPENAI, headers=headers, data=data)

        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    async def anthropic(self, model, api_key):
        from .const import ENDPOINT_ANTHROPIC
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
        from .const import ENDPOINT_GOOGLE
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

    async def localai(self, model, ip_address, port, https):
        from .const import ENDPOINT_LOCALAI
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
        from .const import ENDPOINT_OLLAMA
        data = {
            "model": model,
            "messages": [],
            "stream": False,
            "options": {
                "max_tokens": self.max_tokens,
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
            _LOGGER.debug(f"Provider: {provider}")
            parsed_response = self._resolve_error(url, response, provider)
            raise ServiceValidationError(parsed_response)
        else:
            response_data = await response.json()
            _LOGGER.info(f"Response data: {response_data}")
            return response_data

    async def _fetch(self, url):
        """Fetch image from url and return image data"""
        _LOGGER.info(f"Fetching {url}")
        try:
            response = await self.session.get(url)
        except Exception as e:
            raise ServiceValidationError(f"Fetch failed: {e}")

        if response.status != 200:
            raise ServiceValidationError(
                f"Fetch failed with status code {response.status}")

        data = await response.read()
        return data

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
        # Checks for LocalAI
        elif provider == 'LocalAI':
            if not ip_address or not port:
                raise ServiceValidationError(ERROR_LOCALAI_NOT_CONFIGURED)
        # Checks for Ollama
        elif provider == 'Ollama':
            if not ip_address or not port:
                raise ServiceValidationError(ERROR_OLLAMA_NOT_CONFIGURED)
        # Check media input
        if base64_images == []:
            raise ServiceValidationError(ERROR_NO_IMAGE_INPUT)

    def _resolve_error(self, url, response, provider):
        """Translate response status to error message"""
        if provider == "openai":
            if response.status == 401:
                return "Invalid Authentication. Ensure you are using a valid API key."
            if response.status == 403:
                return "Country, region, or territory not supported."
            if response.status == 404:
                return "The requested model does not exist."
            if response.status == 429:
                return "Rate limit exceeded. You are sending requests too quickly."
            if response.status == 500:
                return "Issue on OpenAI's servers. Wait a few minutes and try again."
            if response.status == 503:
                return "OpenAI's Servers are experiencing high traffic. Try again later."
            else:
                return f"Error: {response}"
        elif provider == "anthropic":
            if response.status == 400:
                return "Invalid Request. There was an issue with the format or content of your request."
            if response.status == 401:
                return "Invalid Authentication. Ensure you are using a valid API key."
            if response.status == 403:
                return "Access Error. Your API key does not have permission to use the specified resource."
            if response.status == 404:
                return "The requested model does not exist."
            if response.status == 429:
                return "Rate limit exceeded. You are sending requests too quickly."
            if response.status == 500:
                return "Issue on Anthropic's servers. Wait a few minutes and try again."
            if response.status == 529:
                return "Anthropic's Servers are experiencing high traffic. Try again later."
            else:
                return f"Error: {response}"
        elif provider == "google":
            if response.status == 400:
                return "Max input tokens exceeded. Reduce target width or number of images."
            if response.status == 403:
                return "Access Error. Your API key does not have permission to use the specified resource."
            if response.status == 404:
                return "The requested model does not exist."
            if response.status == 406:
                return "Insufficient Funds. Ensure you have enough credits to use the service."
            if response.status == 429:
                return "Rate limit exceeded. You are sending requests too quickly."
            if response.status == 503:
                return "Google's Servers are temporarily overloaded or down. Try again later."
            else:
                return f"Error: {response}"
        elif provider == "ollama":
            if response.status == 400:
                return "Invalid Request. There was an issue with the format or content of your request."
            if response.status == 404:
                return "The requested model does not exist."
            if response.status == 500:
                return "Internal server issue (on Ollama server)."
            else:
                return f"Error: {response}"
        elif provider == "localai":
            if response.status == 400:
                return "Invalid Request. There was an issue with the format or content of your request."
            if response.status == 404:
                return "The requested model does not exist."
            if response.status == 500:
                return "Internal server issue (on LocalAI server)."
            else:
                return f"Error: {response}"
