# Declare variables
from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
    CONF_ANTHROPIC_API_KEY,
    CONF_GOOGLE_API_KEY,
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
    DETAIL,
    INCLUDE_FILENAME,
    ERROR_OPENAI_NOT_CONFIGURED,
    ERROR_ANTHROPIC_NOT_CONFIGURED,
    ERROR_GOOGLE_NOT_CONFIGURED,
    ERROR_LOCALAI_NOT_CONFIGURED,
    ERROR_OLLAMA_NOT_CONFIGURED,
    ERROR_NO_IMAGE_INPUT
)
from .request_handlers import RequestHandler
import base64
import io
import os
import logging
from homeassistant.helpers.network import get_url
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from PIL import Image

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Save gpt4vision config entry in hass.data"""
    # Get all entries from config flow
    openai_api_key = entry.data.get(CONF_OPENAI_API_KEY)
    anthropic_api_key = entry.data.get(CONF_ANTHROPIC_API_KEY)
    google_api_key = entry.data.get(CONF_GOOGLE_API_KEY)
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
            CONF_ANTHROPIC_API_KEY: anthropic_api_key,
            CONF_GOOGLE_API_KEY: google_api_key,
            CONF_LOCALAI_IP_ADDRESS: localai_ip_address,
            CONF_LOCALAI_PORT: localai_port,
            CONF_OLLAMA_IP_ADDRESS: ollama_ip_address,
            CONF_OLLAMA_PORT: ollama_port
        }.items()
        if value is not None
    })

    return True


def validate(mode, api_key, base64_images, ip_address=None, port=None):
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
            raise ServiceValidationError(ERROR_OPENAI_NOT_CONFIGURED)
    # Checks for Anthropic
    elif mode == 'Anthropic':
        if not api_key:
            raise ServiceValidationError(ERROR_ANTHROPIC_NOT_CONFIGURED)
    elif mode == 'Google':
        if not api_key:
            raise ServiceValidationError(ERROR_GOOGLE_NOT_CONFIGURED)
    # Checks for LocalAI
    elif mode == 'LocalAI':
        if not ip_address or not port:
            raise ServiceValidationError(ERROR_LOCALAI_NOT_CONFIGURED)
    # Checks for Ollama
    elif mode == 'Ollama':
        if not ip_address or not port:
            raise ServiceValidationError(ERROR_OLLAMA_NOT_CONFIGURED)
    # File path validation
    if base64_images == []:
        raise ServiceValidationError(ERROR_NO_IMAGE_INPUT)


def setup(hass, config):
    async def image_analyzer(data_call):
        """Handle the service call to analyze an image with GPT-4 Vision

        Returns:
            json: response_text
        """
        # HELPERS
        async def encode_image(image_path=None, image_data=None):
            """Encode image as base64

            Args:
                image_path (string): path where image is stored e.g.: "/config/www/tmp/image.jpg"

            Returns:
                string: image encoded as base64
            """
            loop = hass.loop
            if image_path:
                # Open the image file
                img = await loop.run_in_executor(None, Image.open, image_path)
                with img:
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
                img = await loop.run_in_executor(None, Image.open, img_byte_arr)
                with img:
                    # calculate new height based on aspect ratio
                    width, height = img.size
                    aspect_ratio = width / height
                    target_height = int(target_width / aspect_ratio)

                    if width > target_width or height > target_height:
                        img = img.resize((target_width, target_height))

                    img.save(img_byte_arr, format='JPEG')
                    base64_image = base64.b64encode(
                        img_byte_arr.getvalue()).decode('utf-8')

            return base64_image

        # Read from configuration (hass.data)
        localai_ip_address = hass.data.get(
            DOMAIN, {}).get(CONF_LOCALAI_IP_ADDRESS)
        localai_port = hass.data.get(DOMAIN, {}).get(CONF_LOCALAI_PORT)
        ollama_ip_address = hass.data.get(
            DOMAIN, {}).get(CONF_OLLAMA_IP_ADDRESS)
        ollama_port = hass.data.get(DOMAIN, {}).get(CONF_OLLAMA_PORT)

        # Read data from service call
        mode = str(data_call.data.get(PROVIDER))
        message = str(data_call.data.get(MESSAGE)[0:2000])
        image_paths = data_call.data.get(IMAGE_FILE, "").split(
            "\n") if data_call.data.get(IMAGE_FILE) else None
        image_entities = data_call.data.get(IMAGE_ENTITY)
        target_width = data_call.data.get(TARGET_WIDTH, 1280)
        temperature = float(data_call.data.get(TEMPERATURE, 0.5))
        max_tokens = int(data_call.data.get(MAXTOKENS, 100))
        detail = str(data_call.data.get(DETAIL, "auto"))
        include_filename = data_call.data.get(INCLUDE_FILENAME, False)

        # Initialize RequestHandler
        client = RequestHandler(hass)

        base64_images = []
        filenames = []

        if image_paths:
            for image_path in image_paths:
                try:
                    image_path = image_path.strip()
                    if include_filename:
                        # Append filename (without extension)
                        filenames.append(image_path.split('/')
                                         [-1].split('.')[0])
                    else:
                        filenames.append("")
                    if not os.path.exists(image_path):
                        raise ServiceValidationError(
                            f"File {image_path} does not exist")
                    base64_image = await encode_image(image_path=image_path)
                    base64_images.append(base64_image)
                except Exception as e:
                    raise ServiceValidationError(f"Error: {e}")

        if image_entities:
            for image_entity in image_entities:
                base_url = get_url(hass)
                # protocol = get_url(hass).split('://')[0]
                image_url = base_url + hass.states.get(
                    image_entity).attributes.get('entity_picture')
                image_data = await client.fetch(image_url)
                if include_filename:
                    # If entity snapshot requested, use entity name as 'filename'
                    entity_name = base_url + hass.states.get(
                        image_entity).attributes.get('friendly_name')
                    filenames.append(entity_name)
                else:
                    filenames.append("")
                base64_image = await encode_image(image_data=image_data)
                base64_images.append(base64_image)

        _LOGGER.info(f"Base64 Images: {base64_images}")

        # Validate configuration and input data and call handler
        if mode == 'OpenAI':
            api_key = hass.data.get(DOMAIN).get(CONF_OPENAI_API_KEY)
            validate(mode=mode, api_key=api_key, base64_images=base64_images)
            model = str(data_call.data.get(MODEL, "gpt-4o"))
            response_text = await client.openai(model=model,
                                                message=message,
                                                base64_images=base64_images,
                                                filenames=filenames,
                                                api_key=api_key,
                                                max_tokens=max_tokens,
                                                temperature=temperature,
                                                detail=detail)
        elif mode == 'Anthropic':
            api_key = hass.data.get(DOMAIN).get(CONF_ANTHROPIC_API_KEY)
            validate(mode=mode, api_key=api_key, base64_images=base64_images)
            model = str(data_call.data.get(
                MODEL, "claude-3-5-sonnet-20240620"))
            response_text = await client.anthropic(model=model,
                                                   message=message,
                                                   base64_images=base64_images,
                                                   filenames=filenames,
                                                   api_key=api_key,
                                                   max_tokens=max_tokens,
                                                   temperature=temperature)
        elif mode == 'Google':
            api_key = hass.data.get(DOMAIN).get(CONF_GOOGLE_API_KEY)
            validate(mode=mode, api_key=api_key, base64_images=base64_images)
            model = str(data_call.data.get(
                MODEL, "gemini-1.5-flash-latest"))
            response_text = await client.google(model=model,
                                                   message=message,
                                                   base64_images=base64_images,
                                                   filenames=filenames,
                                                   api_key=api_key,
                                                   max_tokens=max_tokens,
                                                   temperature=temperature)
        elif mode == 'LocalAI':
            validate(mode, None, base64_images,
                     localai_ip_address, localai_port)
            model = str(data_call.data.get(MODEL, "gpt-4-vision-preview"))
            response_text = await client.localai(model=model,
                                                 message=message,
                                                 base64_images=base64_images,
                                                 filenames=filenames,
                                                 ip_address=localai_ip_address,
                                                 port=localai_port,
                                                 max_tokens=max_tokens,
                                                 temperature=temperature)
        elif mode == 'Ollama':
            validate(mode, None, base64_images,
                     ollama_ip_address, ollama_port)
            model = str(data_call.data.get(MODEL, "llava"))
            response_text = await client.ollama(model=model,
                                                message=message,
                                                base64_images=base64_images,
                                                filenames=filenames,
                                                ip_address=ollama_ip_address,
                                                port=ollama_port,
                                                max_tokens=max_tokens,
                                                temperature=temperature)

        # close the RequestHandler and return response_text
        await client.close()
        return {"response_text": response_text}

    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response=SupportsResponse.ONLY
    )

    return True
