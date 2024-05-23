# Declare variables
from .const import (
    DOMAIN,
    CONF_PROVIDER,
    CONF_OPENAI_API_KEY,
    CONF_MAXTOKENS,
    CONF_TARGET_WIDTH,
    CONF_MODEL,
    CONF_MESSAGE,
    CONF_IMAGE_FILE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_TEMPERATURE
)
from .request_handlers import (
    handle_localai_request,
    handle_openai_request,
    handle_ollama_request
)
import base64
import io
import os
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from PIL import Image


async def async_setup_entry(hass, entry):
    """Set up gpt4vision from a config entry."""
    # Get all entries from config flow
    openai_api_key = entry.data.get(CONF_OPENAI_API_KEY)
    ip_address = entry.data.get(CONF_IP_ADDRESS)
    port = entry.data.get(CONF_PORT)

    # Ensure DOMAIN exists in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Merge the new data with the existing data
    hass.data[DOMAIN].update({
        key: value
        for key, value in {
            CONF_OPENAI_API_KEY: openai_api_key,
            CONF_IP_ADDRESS: ip_address,
            CONF_PORT: port,
        }.items()
        if value is not None
    })

    return True


def validate(mode, api_key, ip_address, port, image_paths):
    """Validate the configuration for the component

    Args:
        mode (string): "OpenAI" or "LocalAI"
        api_key (string): OpenAI API key
        ip_address (string): LocalAI server IP address
        port (string): LocalAI server port

    Raises:
        ServiceValidationError: if configuration is invalid
    """

    if mode == 'OpenAI':
        if not api_key:
            raise ServiceValidationError("openai_not_configured")
    elif mode == 'LocalAI':
        if not ip_address or not port:
            raise ServiceValidationError("localai_not_configured")
    elif mode == 'Ollama':
        if not ollama_ip_address or not ollama_port:
            raise ServiceValidationError("ollama_not_configured")
    # Check if image file exists
    for image_path in image_paths:
        if not os.path.exists(image_path):
            raise ServiceValidationError("invalid_image_path")


def setup(hass, config):
    async def image_analyzer(data_call):
        """send GET request to OpenAI API '/v1/chat/completions' endpoint

        Returns:
            json: response_text
        """

        # Read from configuration (hass.data)
        api_key = hass.data.get(DOMAIN, {}).get(CONF_OPENAI_API_KEY)
        ip_address = hass.data.get(DOMAIN, {}).get(CONF_IP_ADDRESS)
        port = hass.data.get(DOMAIN, {}).get(CONF_PORT)

        # Read data from service call
        mode = str(data_call.data.get(CONF_PROVIDER))
        # Message to be sent to AI model
        message = str(data_call.data.get(CONF_MESSAGE)[0:2000])
        # Local path to your image. Example: "/config/www/images/garage.jpg"
        image_path = data_call.data.get(CONF_IMAGE_FILE)
        # create a list of image paths (separator: newline character)
        image_paths = image_path.split("\n")
        # Resolution (width only) of the image. Example: 1280 for 720p etc.
        target_width = data_call.data.get(CONF_TARGET_WIDTH, 1280)
        # Temperature parameter. Default is 0.5
        temperature = float(data_call.data.get(CONF_TEMPERATURE, 0.5))
        # Maximum number of tokens used by model. Default is 100.
        max_tokens = int(data_call.data.get(CONF_MAXTOKENS))

        # Validate configuration
        validate(mode, api_key, ip_address, port, image_paths)

        if mode == "OpenAI":
            # GPT model: Default model is gpt-4o for OpenAI
            model = str(data_call.data.get(CONF_MODEL, "gpt-4o"))
        if mode == "LocalAI":
            # GPT model: Default model is gpt-4-vision-preview for LocalAI
            model= str(data_call.data.get(CONF_MODEL, "gpt-4-vision-preview"))
        if mode == 'Ollama':
            # GPT model: Default model is llava for Ollama
            model = str(data_call.data.get(CONF_MODEL, "llava"))

        def encode_image(image_path):
            """Encode image as base64

            Args:
                image_path (string): path where image is stored e.g.: "/config/www/tmp/image.jpg"

            Returns:
                string: image encoded as base64
            """

            # Open the image file
            with Image.open(image_path) as img:
                # calculate new height based on aspect ratio
                width, height= img.size
                aspect_ratio= width / height
                target_height= int(target_width / aspect_ratio)

                # Resize the image only if it's larger than the target size
                if width > target_width or height > target_height:
                    img= img.resize((target_width, target_height))

                # Convert the image to base64
                img_byte_arr= io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                base64_image= base64.b64encode(
                    img_byte_arr.getvalue()).decode('utf-8')

            return base64_image

        # Get the base64 string from the images
        base64_images= []
        for image_path in image_paths:
            base64_image= encode_image(image_path)
            base64_images.append(base64_image)

        # Get the Home Assistant http client
        session= async_get_clientsession(hass)

        if mode == "LocalAI":
            response_text = await handle_localai_request(session, model, message, base64_images, ip_address, port, max_tokens, temperature)

        elif mode == "OpenAI":
            response_text = await handle_openai_request(session, model, message, base64_images, api_key, max_tokens, temperature)

        elif mode == 'Ollama':
            response_text = await handle_ollama_request(session, model, message, base64_images, ip_address, port, max_tokens, temperature)
        return {"response_text": response_text}

    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response = SupportsResponse.ONLY
    )

    return True
