# Declare variables
from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
    CONF_AZURE_API_KEY,
    CONF_AZURE_VERSION,
    CONF_AZURE_BASE_URL,
    CONF_AZURE_DEPLOYMENT,
    CONF_ANTHROPIC_API_KEY,
    CONF_GOOGLE_API_KEY,
    CONF_GROQ_API_KEY,
    CONF_LOCALAI_IP_ADDRESS,
    CONF_LOCALAI_PORT,
    CONF_LOCALAI_HTTPS,
    CONF_OLLAMA_IP_ADDRESS,
    CONF_OLLAMA_PORT,
    CONF_OLLAMA_HTTPS,
    CONF_CUSTOM_OPENAI_ENDPOINT,
    CONF_CUSTOM_OPENAI_API_KEY,
    CONF_RETENTION_TIME,
    MESSAGE,
    REMEMBER,
    MODEL,
    PROVIDER,
    MAXTOKENS,
    TARGET_WIDTH,
    IMAGE_FILE,
    IMAGE_ENTITY,
    VIDEO_FILE,
    EVENT_ID,
    FRIGATE_RETRY_ATTEMPTS,
    FRIGATE_RETRY_SECONDS,
    INTERVAL,
    DURATION,
    MAX_FRAMES,
    TEMPERATURE,
    INCLUDE_FILENAME,
    EXPOSE_IMAGES,
    EXPOSE_IMAGES_PERSIST,
    GENERATE_TITLE,
    SENSOR_ENTITY,
)
from .calendar import SemanticIndex
from .providers import Request
from .media_handlers import MediaProcessor
import os
import re
from datetime import timedelta
from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from functools import partial
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Save config entry to hass.data"""
    # Use the entry_id from the config entry as the UID
    entry_uid = entry.entry_id

    # Get all entries from config flow
    openai_api_key = entry.data.get(CONF_OPENAI_API_KEY)
    azure_api_key = entry.data.get(CONF_AZURE_API_KEY)
    azure_base_url = entry.data.get(CONF_AZURE_BASE_URL)
    azure_deployment = entry.data.get(CONF_AZURE_DEPLOYMENT)
    azure_version = entry.data.get(CONF_AZURE_VERSION)
    anthropic_api_key = entry.data.get(CONF_ANTHROPIC_API_KEY)
    google_api_key = entry.data.get(CONF_GOOGLE_API_KEY)
    groq_api_key = entry.data.get(CONF_GROQ_API_KEY)
    localai_ip_address = entry.data.get(CONF_LOCALAI_IP_ADDRESS)
    localai_port = entry.data.get(CONF_LOCALAI_PORT)
    localai_https = entry.data.get(CONF_LOCALAI_HTTPS)
    ollama_ip_address = entry.data.get(CONF_OLLAMA_IP_ADDRESS)
    ollama_port = entry.data.get(CONF_OLLAMA_PORT)
    ollama_https = entry.data.get(CONF_OLLAMA_HTTPS)
    custom_openai_endpoint = entry.data.get(CONF_CUSTOM_OPENAI_ENDPOINT)
    custom_openai_api_key = entry.data.get(CONF_CUSTOM_OPENAI_API_KEY)
    retention_time = entry.data.get(CONF_RETENTION_TIME)

    # Ensure DOMAIN exists in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Create a dictionary for the entry data
    entry_data = {
        CONF_OPENAI_API_KEY: openai_api_key,
        CONF_AZURE_API_KEY: azure_api_key,
        CONF_AZURE_BASE_URL: azure_base_url,
        CONF_AZURE_DEPLOYMENT: azure_deployment,
        CONF_AZURE_VERSION: azure_version,
        CONF_ANTHROPIC_API_KEY: anthropic_api_key,
        CONF_GOOGLE_API_KEY: google_api_key,
        CONF_GROQ_API_KEY: groq_api_key,
        CONF_LOCALAI_IP_ADDRESS: localai_ip_address,
        CONF_LOCALAI_PORT: localai_port,
        CONF_LOCALAI_HTTPS: localai_https,
        CONF_OLLAMA_IP_ADDRESS: ollama_ip_address,
        CONF_OLLAMA_PORT: ollama_port,
        CONF_OLLAMA_HTTPS: ollama_https,
        CONF_CUSTOM_OPENAI_ENDPOINT: custom_openai_endpoint,
        CONF_CUSTOM_OPENAI_API_KEY: custom_openai_api_key,
        CONF_RETENTION_TIME: retention_time
    }

    # Filter out None values
    filtered_entry_data = {key: value for key,
                           value in entry_data.items() if value is not None}

    # Store the filtered entry data under the entry_id
    hass.data[DOMAIN][entry_uid] = filtered_entry_data

    # check if the entry is the calendar entry (has entry rentention_time)
    if filtered_entry_data.get(CONF_RETENTION_TIME) is not None:
        # make sure 'llmvision' directory exists
        await hass.loop.run_in_executor(None, partial(os.makedirs, "/llmvision", exist_ok=True))
        # forward the calendar entity to the platform
        await hass.config_entries.async_forward_entry_setups(entry, ["calendar"])

    return True


async def async_remove_entry(hass, entry):
    """Remove config entry from hass.data"""
    # Use the entry_id from the config entry as the UID
    entry_uid = entry.entry_id

    if entry_uid in hass.data[DOMAIN]:
        # Remove the entry from hass.data
        _LOGGER.info(f"Removing {entry.title} from hass.data")
        await async_unload_entry(hass, entry)
        hass.data[DOMAIN].pop(entry_uid)
    else:
        _LOGGER.warning(
            f"Entry {entry.title} not found but was requested to be removed")

    return True


async def async_unload_entry(hass, entry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, "calendar")
    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry) -> bool:
    if DOMAIN not in hass.data:
        return True
    else:
        return False


async def _remember(hass, call, start, response) -> None:
    if call.remember:
        # Find semantic index config
        config_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            # Check if the config entry is empty
            if entry.data["provider"] == "Event Calendar":
                config_entry = entry
                break

        if config_entry is None:
            raise ServiceValidationError(
                f"Config entry not found. Please create the 'Event Calendar' config entry first.")

        semantic_index = SemanticIndex(hass, config_entry)

        if "title" in response:
            title = response.get("title", "Unknown object seen")
            if call.image_entities and len(call.image_entities) > 0:
                camera_name = call.image_entities[0]
            elif call.video_paths and len(call.video_paths) > 0:
                camera_name = call.video_paths[0].split(
                    "/")[-1].replace(".mp4", "")
            else:
                camera_name = "File Input"

        if "title" not in response:
            if call.image_entities and len(call.image_entities) > 0:
                camera_name = call.image_entities[0]
                title = "Motion detected near " + camera_name
            elif call.video_paths and len(call.video_paths) > 0:
                camera_name = call.video_paths[0].split(
                    "/")[-1].replace(".mp4", "")
                title = "Motion detected in " + camera_name
            else:
                camera_name = "File Input"
                title = "Motion detected"

        if "response_text" not in response:
            raise ValueError("response_text is missing in the response")

        await semantic_index.remember(
            start=start,
            end=dt_util.now() + timedelta(minutes=1),
            label=title,
            camera_name=camera_name,
            summary=response["response_text"]
        )


async def _update_sensor(hass, sensor_entity: str, value: str | int, type: str) -> None:
    """Update the value of a sensor entity."""
    # Attempt to parse the response
    if type == "boolean" and new_value.lower() not in ["on", "off"]:
        value_lower = value.lower()
        if value_lower in ["true", "false"]:
            new_value = "on" if value_lower == "true" else "off"
        elif re.match(r"^\s*yes\s*[,]*", value_lower):
            new_value = "on"
        elif re.match(r"^\s*no\s*[,]*", value_lower):
            new_value = "off"
        else:
            raise ServiceValidationError(
                "Response could not be parsed. Please check your prompt.")
    elif type == "number":
        try:
            new_value = float(value)
        except ValueError:
            raise ServiceValidationError(
                "Response could not be parsed. Please check your prompt.")
    elif type == "option":
        options = hass.states.get(sensor_entity).attributes["options"]
        if value not in options:
            raise ServiceValidationError(
                "Response could not be parsed. Please check your prompt.")
        new_value = value
   
    # Update the value
    _LOGGER.info(
        f"Updating sensor {sensor_entity} with new value: {new_value}")
    try:
        current_attributes = hass.states.get(
            sensor_entity).attributes.copy()
        hass.states.async_set(sensor_entity, new_value, current_attributes)
    except Exception as e:
        _LOGGER.error(f"Failed to update sensor {sensor_entity}: {e}")
        raise


class ServiceCallData:
    """Store service call data and set default values"""

    def __init__(self, data_call):
        self.provider = str(data_call.data.get(PROVIDER))
        self.model = str(data_call.data.get(
            MODEL))
        self.message = str(data_call.data.get(MESSAGE)[0:2000])
        self.remember = data_call.data.get(REMEMBER, False)
        self.image_paths = data_call.data.get(IMAGE_FILE, "").split(
            "\n") if data_call.data.get(IMAGE_FILE) else None
        self.image_entities = data_call.data.get(IMAGE_ENTITY)
        self.video_paths = data_call.data.get(VIDEO_FILE, "").split(
            "\n") if data_call.data.get(VIDEO_FILE) else None
        self.event_id = data_call.data.get(EVENT_ID, "").split(
            "\n") if data_call.data.get(EVENT_ID) else None
        self.interval = int(data_call.data.get(INTERVAL, 2))
        self.duration = int(data_call.data.get(DURATION, 10))
        self.frigate_retry_attempts = int(
            data_call.data.get(FRIGATE_RETRY_ATTEMPTS, 2))
        self.frigate_retry_seconds = int(
            data_call.data.get(FRIGATE_RETRY_SECONDS, 1))
        self.max_frames = int(data_call.data.get(MAX_FRAMES, 3))
        self.target_width = data_call.data.get(TARGET_WIDTH, 3840)
        self.temperature = float(data_call.data.get(TEMPERATURE, 0.3))
        self.max_tokens = int(data_call.data.get(MAXTOKENS, 100))
        self.include_filename = data_call.data.get(INCLUDE_FILENAME, False)
        self.expose_images = data_call.data.get(EXPOSE_IMAGES, False)
        self.expose_images_persist = data_call.data.get(
            EXPOSE_IMAGES_PERSIST, False)
        self.generate_title = data_call.data.get(GENERATE_TITLE, False)
        self.sensor_entity = data_call.data.get(SENSOR_ENTITY)
        # ------------ Added during call ------------
        # self.base64_images : List[str] = []
        # self.filenames : List[str] = []

    def get_service_call_data(self):
        return self


def setup(hass, config):
    async def image_analyzer(data_call):
        """Handle the service call to analyze an image with LLM Vision"""
        start = dt_util.now()

        # Initialize call object with service call data
        call = ServiceCallData(data_call).get_service_call_data()
        # Initialize the RequestHandler client
        request = Request(hass=hass,
                          message=call.message,
                          max_tokens=call.max_tokens,
                          temperature=call.temperature,
                          )

        # Fetch and preprocess images
        processor = MediaProcessor(hass, request)
        # Send images to RequestHandler client
        request = await processor.add_images(image_entities=call.image_entities,
                                             image_paths=call.image_paths,
                                             target_width=call.target_width,
                                             include_filename=call.include_filename,
                                             expose_images=call.expose_images
                                             )

        # Validate configuration, input data and make the call
        response = await request.call(call)
        await _remember(hass, call, start, response)
        return response

    async def video_analyzer(data_call):
        """Handle the service call to analyze a video (future implementation)"""
        start = dt_util.now()
        call = ServiceCallData(data_call).get_service_call_data()
        call.message = "The attached images are frames from a video. " + call.message

        request = Request(hass,
                          message=call.message,
                          max_tokens=call.max_tokens,
                          temperature=call.temperature,
                          )
        processor = MediaProcessor(hass, request)
        request = await processor.add_videos(video_paths=call.video_paths,
                                             event_ids=call.event_id,
                                             max_frames=call.max_frames,
                                             target_width=call.target_width,
                                             include_filename=call.include_filename,
                                             expose_images=call.expose_images,
                                             expose_images_persist=call.expose_images_persist,
                                             frigate_retry_attempts=call.frigate_retry_attempts,
                                             frigate_retry_seconds=call.frigate_retry_seconds
                                             )
        response = await request.call(call)
        await _remember(hass, call, start, response)
        return response

    async def stream_analyzer(data_call):
        """Handle the service call to analyze a stream"""
        start = dt_util.now()
        call = ServiceCallData(data_call).get_service_call_data()
        call.message = "The attached images are frames from a live camera feed. " + call.message
        request = Request(hass,
                          message=call.message,
                          max_tokens=call.max_tokens,
                          temperature=call.temperature,
                          )
        processor = MediaProcessor(hass, request)
        request = await processor.add_streams(image_entities=call.image_entities,
                                              duration=call.duration,
                                              max_frames=call.max_frames,
                                              target_width=call.target_width,
                                              include_filename=call.include_filename,
                                              expose_images=call.expose_images
                                              )

        response = await request.call(call)
        await _remember(hass, call, start, response)
        return response

    async def data_analyzer(data_call):
        """Handle the service call to analyze visual data"""
        call = ServiceCallData(data_call).get_service_call_data()
        sensor_entity = data_call.data.get("sensor_entity")
        _LOGGER.info(f"Sensor entity: {sensor_entity}")

        # get current value to determine data type
        state = hass.states.get(sensor_entity).state
        sensor_type = sensor_entity.split(".")[0]
        _LOGGER.info(f"Current state: {state}")
        _LOGGER.info(f"Sensor type: {sensor_type}")
        if state == "unavailable":
            raise ServiceValidationError("Sensor entity is unavailable")
        if sensor_type == "input_boolean" or sensor_type == "binary_sensor" or sensor_type == "switch" or sensor_type == "boolean":
            data_type = "one of: ['on', 'off']"
            type = "boolean"
        elif sensor_type == "input_number" or sensor_type == "number" or sensor_type == "sensor":
            data_type = "a number"
            type = "number"
        elif sensor_type == "input_select":
            options = hass.states.get(sensor_entity).attributes["options"]
            data_type = "one of these options: " + \
                ", ".join([f"'{option}'" for option in options])
            type = "option"
        else:
            raise ServiceValidationError("Unsupported sensor entity type")

        call.message = f"Your job is to extract data from images. You can only respond with {data_type}. You must respond with one of the options! If unsure, choose the option that best matches. Answer the following question with the options provided: " + call.message
        request = Request(hass,
                          message=call.message,
                          max_tokens=call.max_tokens,
                          temperature=call.temperature,
                          )
        processor = MediaProcessor(hass, request)
        request = await processor.add_visual_data(image_entities=call.image_entities,
                                                  image_paths=call.image_paths,
                                                  target_width=call.target_width,
                                                  include_filename=call.include_filename
                                                  )
        response = await request.call(call)
        _LOGGER.info(f"Response: {response}")
        _LOGGER.info(f"Sensor type: {type}")
        # update sensor in data_call.data.get("sensor_entity")
        await _update_sensor(hass, sensor_entity, response["response_text"], type)
        return response

    # Register services
    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response=SupportsResponse.ONLY
    )
    hass.services.register(
        DOMAIN, "video_analyzer", video_analyzer,
        supports_response=SupportsResponse.ONLY
    )
    hass.services.register(
        DOMAIN, "stream_analyzer", stream_analyzer,
        supports_response=SupportsResponse.ONLY
    )
    hass.services.register(
        DOMAIN, "data_analyzer", data_analyzer,
    )

    return True
