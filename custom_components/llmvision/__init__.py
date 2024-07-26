# Declare variables
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
from .helpers import ImageEncoder
import os
import logging
from homeassistant.helpers.network import get_url
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Save llmvision config entry in hass.data"""
    # Get all entries from config flow
    openai_api_key = entry.data.get(CONF_OPENAI_API_KEY)
    anthropic_api_key = entry.data.get(CONF_ANTHROPIC_API_KEY)
    google_api_key = entry.data.get(CONF_GOOGLE_API_KEY)
    localai_ip_address = entry.data.get(CONF_LOCALAI_IP_ADDRESS)
    localai_port = entry.data.get(CONF_LOCALAI_PORT)
    localai_https = entry.data.get(CONF_LOCALAI_HTTPS)
    ollama_ip_address = entry.data.get(CONF_OLLAMA_IP_ADDRESS)
    ollama_port = entry.data.get(CONF_OLLAMA_PORT)
    ollama_https = entry.data.get(CONF_OLLAMA_HTTPS)

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
            CONF_LOCALAI_HTTPS: localai_https,
            CONF_OLLAMA_IP_ADDRESS: ollama_ip_address,
            CONF_OLLAMA_PORT: ollama_port,
            CONF_OLLAMA_HTTPS: ollama_https,
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
        """Handle the service call to analyze an image with LLM Vision

        Returns:
            json: response_text
        """

        # Read from configuration (hass.data)
        localai_ip_address = hass.data.get(
            DOMAIN, {}).get(CONF_LOCALAI_IP_ADDRESS)
        localai_port = hass.data.get(DOMAIN, {}).get(CONF_LOCALAI_PORT)
        localai_https = hass.data.get(DOMAIN, {}).get(CONF_LOCALAI_HTTPS)
        ollama_ip_address = hass.data.get(
            DOMAIN, {}).get(CONF_OLLAMA_IP_ADDRESS)
        ollama_port = hass.data.get(DOMAIN, {}).get(CONF_OLLAMA_PORT)
        ollama_https = hass.data.get(DOMAIN, {}).get(CONF_OLLAMA_HTTPS)

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

        base64_images = []
        filenames = []

        client = RequestHandler(hass,
                                message=message,
                                max_tokens=max_tokens,
                                temperature=temperature,
                                detail=detail)
        
        encoder = ImageEncoder(hass)

        # If image_paths is not empty, encode the images as base64 and add them to the client
        if image_paths:
            for image_path in image_paths:
                try:
                    image_path = image_path.strip()
                    if include_filename and os.path.exists(image_path):
                        client.add_image(
                            base64_image=await encoder.encode_image(target_width=target_width, image_path=image_path),
                            filename=image_path.split('/')[-1].split('.')[-2]
                        )
                    elif os.path.exists(image_path):
                        client.add_image(
                            base64_image=await encoder.encode_image(target_width=target_width, image_path=image_path),
                            filename=""
                        )
                    if not os.path.exists(image_path):
                        raise ServiceValidationError(
                            f"File {image_path} does not exist")
                except Exception as e:
                    raise ServiceValidationError(f"Error: {e}")

        # If image_entities is not empty, fetch, encode the images as base64 and add them to the client
        if image_entities:
            for image_entity in image_entities:
                try:
                    base_url = get_url(hass)
                    image_url = base_url + \
                        hass.states.get(image_entity).attributes.get(
                            'entity_picture')
                    image_data = await client.fetch(image_url)

                    # If entity snapshot requested, use entity name as 'filename'
                    if include_filename:
                        entity_name = hass.states.get(
                            image_entity).attributes.get('friendly_name')

                        client.add_image(
                            base64_image=await encoder.encode_image(target_width=target_width, image_data=image_data),
                            filename=entity_name
                        )
                    else:
                        client.add_image(
                            base64_image=await encoder.encode_image(target_width=target_width, image_data=image_data),
                            filename=""
                        )
                except AttributeError as e:
                    raise ServiceValidationError(
                        f"Entity {image_entity} does not exist")

        _LOGGER.debug(f"Base64 Images: {client.get_images()}")

        # Validate configuration and input data, make the call
        if mode == 'OpenAI':
            api_key = hass.data.get(DOMAIN).get(CONF_OPENAI_API_KEY)
            validate(mode=mode,
                     api_key=api_key,
                     base64_images=client.get_images())
            model = str(data_call.data.get(MODEL, "gpt-4o-mini"))
            response_text = await client.openai(model=model, api_key=api_key)
        elif mode == 'Anthropic':
            api_key = hass.data.get(DOMAIN).get(CONF_ANTHROPIC_API_KEY)
            validate(mode=mode,
                     api_key=api_key,
                     base64_images=client.get_images())
            model = str(data_call.data.get(
                MODEL, "claude-3-5-sonnet-20240620"))
            response_text = await client.anthropic(model=model, api_key=api_key)
        elif mode == 'Google':
            api_key = hass.data.get(DOMAIN).get(CONF_GOOGLE_API_KEY)
            validate(mode=mode, api_key=api_key,
                     base64_images=client.get_images())
            model = str(data_call.data.get(
                MODEL, "gemini-1.5-flash-latest"))
            response_text = await client.google(model=model, api_key=api_key)
        elif mode == 'LocalAI':
            validate(mode=mode,
                     api_key=None,
                     base64_images=client.get_images(),
                     ip_address=localai_ip_address,
                     port=localai_port)
            model = str(data_call.data.get(MODEL, "gpt-4-vision-preview"))
            response_text = await client.localai(model=model,
                                                 ip_address=localai_ip_address,
                                                 port=localai_port,
                                                 https=localai_https)
        elif mode == 'Ollama':
            validate(mode=mode,
                     api_key=None,
                     base64_images=client.get_images(),
                     ip_address=ollama_ip_address,
                     port=ollama_port)
            model = str(data_call.data.get(MODEL, "llava"))
            response_text = await client.ollama(model=model,
                                                ip_address=ollama_ip_address,
                                                port=ollama_port,
                                                https=ollama_https)

        return {"response_text": response_text}

    async def video_analyzer(data_call):
        """Handle the service call to analyze a video (future implementation)"""
        pass

    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response=SupportsResponse.ONLY
    )

    return True
