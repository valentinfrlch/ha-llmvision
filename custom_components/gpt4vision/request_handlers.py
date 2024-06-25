from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import logging
from .const import (
    VERSION_ANTHROPIC
)

_LOGGER = logging.getLogger(__name__)


class RequestHandler:
    def __init__(self, hass):
        self.session = async_get_clientsession(hass)

    async def openai(self, model, message, base64_images, filenames, api_key, max_tokens, temperature, detail):
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
        for image, filename in zip(base64_images, filenames):
            tag = ("Image " + str(base64_images.index(image) + 1)
                   ) if filename == "" else filename
            data["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            data["messages"][0]["content"].append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}", "detail": detail}})

        # append the message to the end of the request
        data["messages"][0]["content"].append(
            {"type": "text", "text": message}
        )

        response = await self._post(
            url="https://api.openai.com/v1/chat/completions", headers=headers, data=data)

        response_text = response.get(
            "choices")[0].get("message").get("content")
        return response_text

    async def anthropic(self, model, message, base64_images, filenames, api_key, max_tokens, temperature):
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
        for image, filename in zip(base64_images, filenames):
            tag = ("Image " + str(base64_images.index(image) + 1)
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
            {"type": "text", "text": message}
        )

        response = await self._post(
            url="https://api.anthropic.com/v1/messages", headers=headers, data=data)

        response_text = response.get("content")[0].get("text")
        return response_text

    async def google(self, model, message, base64_images, filenames, api_key, max_tokens, temperature):
        # Set headers and payload
        headers = {'content-type': 'application/json'}
        data = {"contents": [
        ],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
        }
        }

        # Add the images to the request
        for image, filename in zip(base64_images, filenames):
            tag = ("Image " + str(base64_images.index(image) + 1)
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
             "parts": [{"text": message}
                       ]
             }
        )

        response = await self._post(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}", headers=headers, data=data)

        response_text = response.get("candidates")[0].get("content").get("parts")[0].get("text")
        return response_text

    async def localai(self, model, message, base64_images, filenames, ip_address, port, max_tokens, temperature):
        data = {"model": model,
                "messages": [{"role": "user", "content": [
                ]}],
                "max_tokens": max_tokens,
                "temperature": temperature
                }
        for image, filename in zip(base64_images, filenames):
            tag = ("Image " + str(base64_images.index(image) + 1)
                   ) if filename == "" or not filename else filename
            data["messages"][0]["content"].append(
                {"type": "text", "text": tag + ":"})
            data["messages"][0]["content"].append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})

        # append the message to the end of the request
        data["messages"][0]["content"].append(
            {"type": "text", "text": message}
        )

        response = await self._post(
            url=f"http://{ip_address}:{port}/v1/chat/completions", headers={}, data=data)

        response_text = response.get("choices")[0].get("message").get("content")
        return response_text

    async def ollama(self, model, message, base64_images, filenames, ip_address, port, max_tokens, temperature):
        data = {
            "model": model,
            "messages": [],
            "stream": False,
            "options": {
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        }

        for image, filename in zip(base64_images, filenames):
            tag = ("Image " + str(base64_images.index(image) + 1)
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
            "content": message
        }
        data["messages"].append(prompt_message)

        response = await self._post(
            url=f"http://{ip_address}:{port}/api/chat", headers={}, data=data)

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
            error_message = (await response.json()).get('error').get('message')
            raise ServiceValidationError(
                f"Request failed with status: {response.status} and error: {error_message}")

        response_data = await response.json()
        _LOGGER.debug(f"Response data: {response_data}")
        return response_data

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
