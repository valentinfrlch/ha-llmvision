# Declare variables
from .const import DOMAIN, CONF_API_KEY, CONF_MAXTOKENS, CONF_TARGET_WIDTH, CONF_MODEL, CONF_MESSAGE, CONF_IMAGE_FILE
import base64
import io
import os
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from PIL import Image


async def async_setup_entry(hass, entry):
    """Set up gpt4vision from a config entry."""
    # Get the API key from the configuration entry
    api_key = entry.data[CONF_API_KEY]

    # Store the API key in hass.data
    hass.data[DOMAIN] = {
        "api_key": api_key
    }

    return True


def setup(hass, config):
    async def image_analyzer(data_call):
        """send GET request to OpenAI API '/v1/chat/completions' endpoint

        Returns:
            json: response_text
        """

        # Try to get the API key from hass.data
        api_key = hass.data.get(DOMAIN, {}).get("api_key")

        # Check if api key is present
        if not api_key:
            raise ServiceValidationError(
                "API key is required. Please set up the integration again.")

        # Read data from service call
        # Resolution (width only) of the image. Example: 1280 for 720p etc.
        target_width = data_call.data.get(CONF_TARGET_WIDTH, 1280)
        # Local path to your image. Example: "/config/www/images/garage.jpg"
        image_path = data_call.data.get(CONF_IMAGE_FILE)
        # Maximum number of tokens used by model. Default is 100.
        max_tokens = int(data_call.data.get(CONF_MAXTOKENS))
        # GPT model: Default model is gpt-4o
        model = str(data_call.data.get(CONF_MODEL, "gpt-4o"))
        # Message to be sent to AI model
        message = str(data_call.data.get(CONF_MESSAGE)[0:2000])

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

        # HTTP Request for AI API
        # Header Parameters
        headers = {'Content-type': 'application/json',
                   'Authorization': 'Bearer ' + api_key}

        # Body Parameters
        data = {"model": model, "messages": [{"role": "user", "content": [{"type": "text", "text": message},
                                                                          {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}], "max_tokens": max_tokens}

        # Get the Home Assistant http client
        session = async_get_clientsession(hass)

        # Get response from OpenAI and read content inside message
        response = await session.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=data)

        # Check if response is successful
        if response.status != 200:
            raise ServiceValidationError(
                (await response.json()).get('error').get('message'))

        response_text = (await response.json()).get(
            "choices")[0].get("message").get("content")
        return {"response_text": response_text}

    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response=SupportsResponse.ONLY
    )

    return True
