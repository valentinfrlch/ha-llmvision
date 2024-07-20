from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import logging
from .const import (
    VERSION_ANTHROPIC,
    ENDPOINT_OPENAI,
    ENDPOINT_ANTHROPIC,
    ENDPOINT_GOOGLE,
    ENDPOINT_LOCALAI,
    ENDPOINT_OLLAMA
)

_LOGGER = logging.getLogger(__name__)


class RequestHandler:
    def __init__(self, hass, message, max_tokens, temperature, detail):
        self.session = async_get_clientsession(hass)
        self.message = message
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.detail = detail
        self.base64_images = []
        self.filenames = []

    def add_image(self, base64_image, filename):
        self.base64_images.append(base64_image)
        self.filenames.append(filename)


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

    async def localai(self, model, ip_address, port):
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

        response = await self._post(
            url=ENDPOINT_LOCALAI.format(ip_address=ip_address, port=port), headers={}, data=data)

        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    async def ollama(self, model, ip_address, port):
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

        response = await self._post(url=ENDPOINT_OLLAMA.format(ip_address=ip_address, port=port), headers={}, data=data)
        response_text = response.get("message").get("content")
        return response_text

    async def _post(self, url, headers, data):
        """Post data to url and return response data"""
        _LOGGER.debug(f"Request data: {data}")
        try:
            response = await self.session.post(url, headers=headers, json=data)
        except Exception as e:
            raise ServiceValidationError(f"Request failed: {e}")

        if response.status != 200:
            try:
                parsed_response = self._resolve_error(url, response)
                raise ServiceValidationError(parsed_response)
            except Exception as e:
                raise ServiceValidationError(e)

        response_data = await response.json()
        _LOGGER.debug(f"Response data: {response_data}")
        return response_data

    async def fetch(self, url):
        """Fetch image from url and return image data"""
        _LOGGER.debug(f"Fetching image from {url}")
        try:
            response = await self.session.get(url)
        except Exception as e:
            raise ServiceValidationError(f"Failed to fetch image: {e}")

        if response.status != 200:
            raise ServiceValidationError(
                f"Fetch failed with status code {response.status}")

        data = await response.read()
        return data

    def _resolve_error(self, url, response):
        """Translate response status to error message"""
        if url == ENDPOINT_OPENAI:
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
        elif url == ENDPOINT_ANTHROPIC:
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
        elif url == ENDPOINT_GOOGLE:
            if response.status == 400:
                return "User location is not supported for the API use without a billing account linked."
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
        elif url == ENDPOINT_OLLAMA:
            if response.status == 400:
                return "Invalid Request. There was an issue with the format or content of your request."
            if response.status == 404:
                return "The requested model does not exist."
            if response.status == 500:
                return "Internal server issue (on Ollama server)."
            else:
                return f"Error: {response}"
        elif url == ENDPOINT_LOCALAI:
            if response.status == 400:
                return "Invalid Request. There was an issue with the format or content of your request."
            if response.status == 404:
                return "The requested model does not exist."
            if response.status == 500:
                return "Internal server issue (on LocalAI server)."
            else:
                return f"Error: {response}"



    async def close(self):
        # Home Assistant will close the session
        # TODO: There is a warning "Unclosed client session", but if closed it throws an error...
        # await self.session.close()
        pass
