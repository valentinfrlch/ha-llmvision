# Declare variables
from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
    CONF_LOCALAI_IP_ADDRESS,
    CONF_LOCALAI_PORT,
    CONF_OLLAMA_IP_ADDRESS,
    CONF_OLLAMA_PORT,
    PROVIDER,
    MAXTOKENS,
    TARGET_WIDTH,
    MODEL,
    MESSAGE,
    IMAGE_FILE,
    IMAGE_ENTITY,
    TEMPERATURE,
    DETAIL
)
from .request_handlers import (
    handle_localai_request,
    handle_openai_request,
    handle_ollama_request
)
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
    # Get all entries from config flow
    openai_api_key = entry.data.get(CONF_OPENAI_API_KEY)
    localai_ip_address = entry.data.get(CONF_LOCALAI_IP_ADDRESS)
    localai_port = entry.data.get(CONF_LOCALAI_PORT)
    ollama_ip_address = entry.data.get(CONF_OLLAMA_IP_ADDRESS)
    ollama_port = entry.data.get(CONF_OLLAMA_PORT)

    # Ensure DOMAIN exists in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Merge the new data with the existing data
    hass.data[DOMAIN].update({
        key: value
        for key, value in {
            CONF_OPENAI_API_KEY: openai_api_key,
            CONF_LOCALAI_IP_ADDRESS: localai_ip_address,
            CONF_LOCALAI_PORT: localai_port,
            CONF_OLLAMA_IP_ADDRESS: ollama_ip_address,
            CONF_OLLAMA_PORT: ollama_port
        }.items()
        if value is not None
    })

    return True


def validate(mode, api_key, image_paths, image_data, ip_address=None, port=None):
    """Validate the configuration for the component

    Args:
        mode (string): "OpenAI" or "LocalAI"
        api_key (string): OpenAI API key
        ip_address (string): LocalAI server IP address
        port (string): LocalAI server port

    Raises:
        ServiceValidationError: if configuration is invalid
    """
    # Checks for OpenAI
    if mode == 'OpenAI':
        if not api_key:
            raise ServiceValidationError("openai_not_configured")
    # Checks for LocalAI
    elif mode == 'LocalAI':
        if not ip_address or not port:
            raise ServiceValidationError("localai_not_configured")
    # Checks for Ollama
    elif mode == 'Ollama':
        if not ip_address or not port:
            raise ServiceValidationError("ollama_not_configured")
    # File path validation
    # check if either image_data or image_paths is provided
    if not image_data and not image_paths:
        raise ServiceValidationError("no_image_input")
    if image_data:
        # check if image_data is a valid image
        try:
            Image.open(image_data)
        except:
            raise ServiceValidationError("invalid_image_data")

    if image_paths:
        for image_path in image_paths:
            if not os.path.exists(image_path):
                raise ServiceValidationError("invalid_image_path")


def setup(hass, config):
    async def image_analyzer(data_call):
        """Handle the service call to analyze an image with GPT-4 Vision

        Returns:
            json: response_text
        """

        async def download_image(image_url):
            """use async_get_clientsession to download the image"""
            async with async_get_clientsession(hass) as session:
                async with session.get(image_url, ssl=False) as response:
                    image_data = await response.read()
            # encode the image data as base64
            encoded_image = encode_image(image_data=image_data)
            return encoded_image

        def encode_image(image_path=None, image_data=None):
            """Encode image as base64

            Args:
                image_path (string): path where image is stored e.g.: "/config/www/tmp/image.jpg"

            Returns:
                string: image encoded as base64
            """
            if image_path:
                # Open the image file
                with Image.open(image_path) as img:
                    # calculate new height based on aspect ratio
                    width, height = img.size
                    aspect_ratio = width / height
                    target_height = int(target_width / aspect_ratio)

                    # Resize the image only if it's larger than the target size
                    if width > target_width or height > target_height:
                        img = img.resize((target_width, target_height))

                    # Convert the image to base64
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG')
                    base64_image = base64.b64encode(
                        img_byte_arr.getvalue()).decode('utf-8')

            elif image_data:
                # Convert the image to base64
                img_byte_arr = io.BytesIO()
                img_byte_arr.write(image_data)
                img = Image.open(img_byte_arr)
                img.save(img_byte_arr, format='JPEG')
                base64_image = base64.b64encode(
                    img_byte_arr.getvalue()).decode('utf-8')

            return base64_image

        # Read from configuration (hass.data)
        api_key = hass.data.get(DOMAIN, {}).get(CONF_OPENAI_API_KEY)
        localai_ip_address = hass.data.get(
            DOMAIN, {}).get(CONF_LOCALAI_IP_ADDRESS)
        localai_port = hass.data.get(DOMAIN, {}).get(CONF_LOCALAI_PORT)
        ollama_ip_address = hass.data.get(
            DOMAIN, {}).get(CONF_OLLAMA_IP_ADDRESS)
        ollama_port = hass.data.get(DOMAIN, {}).get(CONF_OLLAMA_PORT)

        # Read data from service call
        mode = str(data_call.data.get(PROVIDER))
        message = str(data_call.data.get(MESSAGE)[0:2000])
        image_paths = data_call.data.get(IMAGE_FILE, "").split("\n")
        image_entity = data_call.data.get(IMAGE_ENTITY, "")
        target_width = data_call.data.get(TARGET_WIDTH, 1280)
        temperature = float(data_call.data.get(TEMPERATURE, 0.5))
        max_tokens = int(data_call.data.get(MAXTOKENS))
        detail = str(data_call.data.get(DETAIL, "auto"))

        # If an image entity is specified, get the image data from the entity
        if image_entity:
            image_data_list = []
            for cur_entity in image_entity:
                image_url = "https://localhost:8123" + hass.states.get(
                    cur_entity).attributes.get('entity_picture')
                # make a GET request to the image entity with the built-in aiohttp client
                image_data = await download_image(image_url)
                image_data_list.append(image_data)

        else:
            # Local path to your image. Example: "/config/www/images/garage.jpg"
            image_paths = data_call.data.get(IMAGE_FILE).split("\n")
            image_path = image_paths[0]  # Use the first image path

        # Validate configuration and input data and set model
        if mode == 'OpenAI':
            validate(mode, api_key, image_paths, image_data)
            model = str(data_call.data.get(MODEL, "gpt-4o"))
        elif mode == 'LocalAI':
            validate(mode, None, image_paths, image_data,
                     localai_ip_address, localai_port)
            model = str(data_call.data.get(MODEL, "gpt-4-vision-preview"))
        elif mode == 'Ollama':
            validate(mode, None, image_paths, image_data,
                     ollama_ip_address, ollama_port)
            model = str(data_call.data.get(MODEL, "llava"))


        # Get the base64 string from the images
        base64_images = []
        if image_path:
            for image_path in image_paths:
                base64_image = encode_image(image_path=image_path)
                base64_images.append(base64_image)

        elif image_data:
            base64_image = encode_image(image_data=image_data)
            base64_images.append(base64_image)

        # Get the Home Assistant http client
        session = async_get_clientsession(hass)

        if mode == "LocalAI":
            response_text = await handle_localai_request(session, model, message, base64_images, localai_ip_address, localai_port, max_tokens, temperature)

        elif mode == "OpenAI":
            response_text = await handle_openai_request(session, model, message, base64_images, api_key, max_tokens, temperature, detail)

        elif mode == 'Ollama':
            response_text = await handle_ollama_request(session, model, message, base64_images, ollama_ip_address, ollama_port, max_tokens, temperature)
        return {"response_text": response_text}

    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response=SupportsResponse.ONLY
    )

    return True
