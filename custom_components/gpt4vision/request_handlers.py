from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import logging
import json
from .const import (
    VERSION_ANTHROPIC
)

_LOGGER = logging.getLogger(__name__)


class RequestHandler:
    def __init__(self, hass):
        self.session = async_get_clientsession(hass)

    async def openai(self, model, message, base64_images, api_key, max_tokens, temperature, detail):
        # Set headers and payload
        headers = {'Content-type': 'application/json',
                   'Authorization': 'Bearer ' + api_key}
        data = {"model": model,
                "messages": [{"role": "user", "content": [
                ]}],
                "max_tokens": max_tokens,
                "temperature": temperature
                }

        # Add the images to the request
        for image in base64_images:
            data["messages"][0]["content"].append(
                {"type": "text", "text": "Image " + str(base64_images.index(image) + 1) + ":"})
            data["messages"][0]["content"].append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}", "detail": detail}})

        # append the message to the end of the request
        data["messages"][0]["content"].append(
            {"type": "text", "text": message}
        )

        try:
            response = await self.session.post(
                "https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        except Exception as e:
            _LOGGER.error(f"Request failed: {e}")
            raise ServiceValidationError(f"Request failed: {e}")

        if response.status != 200:
            error_message = (await response.json()).get('error').get('message')
            _LOGGER.error(
                f"Request failed with status: {response.status} and error: {error_message}")
            raise ServiceValidationError(error_message)

        response_text = (await response.json()).get(
            "choices")[0].get("message").get("content")
        return response_text

    async def anthropic(self, model, message, base64_images, api_key, max_tokens, temperature):
        # Set headers and payload
        headers = {'content-type': 'application/json',
                   'x-api-key': api_key,
                   'anthropic-version': VERSION_ANTHROPIC}
        data = {"model": model,
                "messages": [
                    {"role": "user", "content": []}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
                }

        # Add the images to the request
        for image in base64_images:
            data["messages"][0]["content"].append(
                {
                    "type": "text",
                    "text": "Image " + str(base64_images.index(image) + 1) + ":"
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
            {"type": "text", "text": message}
        )

        _LOGGER.debug(f"Anthropic request data: {data}")

        try:
            response = await self.session.post(
                "https://api.anthropic.com/v1/messages", headers=headers, json=data)
        except Exception as e:
            _LOGGER.error(f"Request failed: {e}")
            raise ServiceValidationError(f"Request failed: {e}")

        if response.status != 200:
            error_message = (await response.json()).get('error').get('message')
            _LOGGER.error(
                f"Request failed with status: {response.status} and error: {error_message}")
            raise ServiceValidationError(error_message)

        response_text = (await response.json()).get("content")[0].get("text")
        return response_text

    async def localai(self, model, message, base64_images, ip_address, port, max_tokens, temperature):
        data = {"model": model,
                "messages": [{"role": "user", "content": [
                ]}],
                "max_tokens": max_tokens,
                "temperature": temperature
                }
        for image in base64_images:
            data["messages"][0]["content"].append(
                {"type": "text", "text": "Image " + str(base64_images.index(image) + 1) + ":"})
            data["messages"][0]["content"].append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})
        
        # append the message to the end of the request
        data["messages"][0]["content"].append(
            {"type": "text", "text": message}
        )

        try:
            response = await self.session.post(
                f"http://{ip_address}:{port}/v1/chat/completions", json=data)
        except Exception as e:
            _LOGGER.error(f"Request failed: {e}")
            raise ServiceValidationError(f"Request failed: {e}")

        if response.status != 200:
            _LOGGER.error(
                f"Request failed with status code {response.status}")
            raise ServiceValidationError(
                f"Request failed with status code {response.status}")

        response_text = (await response.json()).get("choices")[0].get(
            "message").get("content")
        return response_text

    async def ollama(self, model, message, base64_images, ip_address, port, max_tokens, temperature):
        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": message,
                    "images": []
                }
            ],
            "stream": False,
            "options": {
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        }

        for image in base64_images:
            data["messages"][0]["images"].append(image)

        try:
            response = await self.session.post(
                f"http://{ip_address}:{port}/api/chat", json=data)
        except Exception as e:
            _LOGGER.error(f"Request failed: {e}")
            raise ServiceValidationError(f"Request failed: {e}")

        if response.status != 200:
            _LOGGER.error(
                f"Request failed with status code {response.status}")
            raise ServiceValidationError(
                f"Request failed with status code {response.status}")

        response_text = (await response.json()).get(
            "message").get("content")
        return response_text

    async def fetch(self, url):
        """Fetch image from url and return image data"""
        try:
            response = await self.session.get(url)
        except Exception as e:
            raise ServiceValidationError(f"Failed to fetch image: {e}")

        if response.status != 200:
            raise ServiceValidationError(
                f"Fetch failed with status code {response.status}")

        data = await response.read()
        return data

    async def close(self):
        await self.session.close()
