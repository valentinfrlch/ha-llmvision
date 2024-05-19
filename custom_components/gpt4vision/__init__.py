# Declare variables
from .const import DOMAIN, CONF_API_KEY, CONF_MAXTOKENS, CONF_TARGET_WIDTH, CONF_MODEL, CONF_MESSAGE, CONF_IMAGE_FILE, CONF_MODE, CONF_IP_ADDRESS, CONF_PORT
import base64
import io
import os
import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from PIL import Image

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Set up gpt4vision from a config entry."""
    # Get the API key from the configuration entry
    mode = entry.data.get(CONF_MODE)
    data = {"mode": mode}

    if mode == "OpenAI":
        api_key = entry.data[CONF_API_KEY]
        data["api_key"] = api_key
    else:
        ip_address = entry.data[CONF_IP_ADDRESS]
        port = entry.data[CONF_PORT]
        # Add the IP address and port to the data dictionary
        data["ip_address"] = ip_address
        data["port"] = port

    # Store the data dictionary in hass.data
    hass.data[DOMAIN] = data

    return True


async def validate_data(data):
    if data[CONF_MODE] == "OpenAI":
        if not data[CONF_API_KEY]:
            raise ServiceValidationError("empty_api_key")
    elif data[CONF_MODE] == "LocalAI":
        if not data[CONF_IP_ADDRESS]:
            raise ServiceValidationError("empty_ip_address")
        if not data[CONF_PORT]:
            raise ServiceValidationError("empty_port")
    else:
        raise ServiceValidationError("empty_mode")
    return True


def setup(hass, config):
    async def image_analyzer(data_call):
        """send GET request to OpenAI API '/v1/chat/completions' endpoint

        Returns:
            json: response_text
        """

        # Read from configuration (hass.data)
        api_key = hass.data.get(DOMAIN, {}).get(CONF_API_KEY)
        ip_address = hass.data.get(DOMAIN, {}).get(CONF_IP_ADDRESS)
        port = hass.data.get(DOMAIN, {}).get(CONF_PORT)
        mode = hass.data.get(DOMAIN, {}).get(CONF_MODE)

        validate = {
            CONF_MODE: mode,
            CONF_API_KEY: api_key,
            CONF_IP_ADDRESS: ip_address,
            CONF_PORT: port
        }
        try:
            await validate_data(validate)
        except ServiceValidationError as e:
            _LOGGER.error(f"Validation failed: {e}")

        # Read data from service call
        # Resolution (width only) of the image. Example: 1280 for 720p etc.
        target_width = data_call.data.get(CONF_TARGET_WIDTH, 1280)
        # Local path to your image. Example: "/config/www/images/garage.jpg"
        image_path = data_call.data.get(CONF_IMAGE_FILE)
        # Message to be sent to AI model
        message = str(data_call.data.get(CONF_MESSAGE)[0:2000])

        if mode == "OpenAI":
            # Maximum number of tokens used by model. Default is 100.
            max_tokens = int(data_call.data.get(CONF_MAXTOKENS))
            # GPT model: Default model is gpt-4o for OpenAI
            model = str(data_call.data.get(CONF_MODEL, "gpt-4o"))
        if mode == "LocalAI":
            # GPT model: Default model is gpt-4-vision-preview for LocalAI
            model = str(data_call.data.get(CONF_MODEL, "gpt-4-vision-preview"))

        # Check if image file exists
        if not os.path.exists(image_path):
            raise ServiceValidationError(
                f"Image does not exist: {image_path}")

        def encode_image(image_path):
            """Encode image as base64

            Args:
                image_path (string): path where image is stored e.g.: "/config/www/tmp/image.jpg"

            Returns:
                string: image encoded as base64
            """

            # Open the image file
            with Image.open(image_path) as img:
                width, height = img.size
                aspect_ratio = width / height
                target_height = int(target_width / aspect_ratio)

                # Resize the image only if it's larger than the target size
                # API call price is based on resolution. The smaller the image, the cheaper the call
                # Check https://openai.com/api/pricing/ for information on pricing
                if width > target_width or height > target_height:
                    img = img.resize((target_width, target_height))

                # Convert the image to base64
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                base64_image = base64.b64encode(
                    img_byte_arr.getvalue()).decode('utf-8')

            return base64_image

        # Get the base64 string from the image
        base64_image = encode_image(image_path)

        # Get the Home Assistant http client
        session = async_get_clientsession(hass)

        if mode == "LocalAI":
            response_text = await handle_localai_request(data_call, session, model, message, base64_image, ip_address, port)

        elif mode == "OpenAI":
            response_text = await handle_openai_request(data_call, session, model, message, base64_image, api_key, max_tokens)

        return {"response_text": response_text}

    async def handle_localai_request(data_call, session, model, message, base64_image, ip_address, port):
        data = {"model": model, "messages": [{"role": "user", "content": [{"type": "text", "text": message},
                                                                          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}]}
        response = await session.post(
            f"http://{data_call.data.get(ip_address)}:{data_call.data.get(port)}/v1/chat/completions", json=data)
        if response.status != 200:
            raise ServiceValidationError(
                f"Request failed with status code {response.status}")
        response_text = (await response.json()).get("choices")[0].get(
            "message").get("content")
        return response_text

    async def handle_openai_request(data_call, session, model, message, base64_image, api_key, max_tokens):
        headers = {'Content-type': 'application/json',
                   'Authorization': 'Bearer ' + api_key}
        data = {"model": model, "messages": [{"role": "user", "content": [{"type": "text", "text": message},
                                                                          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}], "max_tokens": max_tokens}
        response = await session.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        if response.status != 200:
            raise ServiceValidationError(
                (await response.json()).get('error').get('message'))
        response_text = (await response.json()).get(
            "choices")[0].get("message").get("content")
        return response_text

    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response=SupportsResponse.ONLY
    )

    return True
