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
    CONF_CUSTOM_OPENAI_DEFAULT_MODEL,
    CONF_RETENTION_TIME,
    CONF_MEMORY_PATHS,
    CONG_MEMORY_IMAGES_ENCODED,
    CONF_MEMORY_STRINGS,
    CONF_SYSTEM_PROMPT,
    CONF_TITLE_PROMPT,
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_AWS_REGION_NAME,
    CONF_AWS_DEFAULT_MODEL,
    CONF_OPENWEBUI_IP_ADDRESS,
    CONF_OPENWEBUI_PORT,
    CONF_OPENWEBUI_HTTPS,
    CONF_OPENWEBUI_API_KEY,
    CONF_OPENWEBUI_DEFAULT_MODEL,
    MESSAGE,
    REMEMBER,
    USE_MEMORY,
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
    GENERATE_TITLE,
    SENSOR_ENTITY,
    DATA_EXTRACTION_PROMPT,
)
from .calendar import Timeline
from .providers import Request
from .memory import Memory
from .media_handlers import MediaProcessor
import re
import os
from datetime import timedelta
from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
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
    custom_openai_default_model = entry.data.get(
        CONF_CUSTOM_OPENAI_DEFAULT_MODEL)
    retention_time = entry.data.get(CONF_RETENTION_TIME)
    memory_paths = entry.data.get(CONF_MEMORY_PATHS)
    memory_images_encoded = entry.data.get(CONG_MEMORY_IMAGES_ENCODED)
    memory_strings = entry.data.get(CONF_MEMORY_STRINGS)
    system_prompt = entry.data.get(CONF_SYSTEM_PROMPT)
    title_prompt = entry.data.get(CONF_TITLE_PROMPT)
    aws_access_key_id = entry.data.get(CONF_AWS_ACCESS_KEY_ID)
    aws_secret_access_key = entry.data.get(CONF_AWS_SECRET_ACCESS_KEY)
    aws_region_name = entry.data.get(CONF_AWS_REGION_NAME)
    aws_default_model = entry.data.get(CONF_AWS_DEFAULT_MODEL)
    openwebui_ip_address = entry.data.get(CONF_OPENWEBUI_IP_ADDRESS)
    openwebui_port = entry.data.get(CONF_OPENWEBUI_PORT)
    openwebui_https = entry.data.get(CONF_OPENWEBUI_HTTPS)
    openwebui_api_key = entry.data.get(CONF_OPENWEBUI_API_KEY)
    openwebui_default_model = entry.data.get(CONF_OPENWEBUI_DEFAULT_MODEL)

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
        CONF_CUSTOM_OPENAI_DEFAULT_MODEL: custom_openai_default_model,
        CONF_RETENTION_TIME: retention_time,
        CONF_MEMORY_PATHS: memory_paths,
        CONG_MEMORY_IMAGES_ENCODED: memory_images_encoded,
        CONF_MEMORY_STRINGS: memory_strings,
        CONF_SYSTEM_PROMPT: system_prompt,
        CONF_TITLE_PROMPT: title_prompt,
        CONF_AWS_ACCESS_KEY_ID: aws_access_key_id,
        CONF_AWS_SECRET_ACCESS_KEY: aws_secret_access_key,
        CONF_AWS_REGION_NAME: aws_region_name,
        CONF_AWS_DEFAULT_MODEL: aws_default_model,
        CONF_OPENWEBUI_IP_ADDRESS: openwebui_ip_address,
        CONF_OPENWEBUI_PORT: openwebui_port,
        CONF_OPENWEBUI_HTTPS: openwebui_https,
        CONF_OPENWEBUI_API_KEY: openwebui_api_key,
        CONF_OPENWEBUI_DEFAULT_MODEL: openwebui_default_model
    }

    # Filter out None values
    filtered_entry_data = {key: value for key,
                           value in entry_data.items() if value is not None}

    # Store the filtered entry data under the entry_id
    hass.data[DOMAIN][entry_uid] = filtered_entry_data

    # check if the entry is the calendar entry (has entry rentention_time)
    if filtered_entry_data.get(CONF_RETENTION_TIME) is not None:
        # forward the calendar entity to the platform for setup
        await hass.config_entries.async_forward_entry_setups(entry, ["calendar"])
        # Run cleanup
        timeline = Timeline(hass, entry)
        await timeline._cleanup()
    
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
        # Check if entry is the timeline entry
        if entry.data["provider"] == 'Timeline':
            # Check if "/llmvision/events.db" exists
            db_path = os.path.join(
                hass.config.path("llmvision"), "events.db"
            )
            if os.path.exists(db_path):
                os.remove(db_path)
    else:
        _LOGGER.warning(
            f"Entry {entry.title} not found but was requested to be removed")
    return True


async def async_unload_entry(hass, entry) -> bool:
    _LOGGER.debug(f"Unloading {entry.title} from hass.data")
    # check if the entry is the calendar entry (has entry rentention_time)
    if entry.data.get(CONF_RETENTION_TIME) is not None:
        # unload the calendar
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["calendar"])
    else:
        unload_ok = True
    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry) -> bool:
    _LOGGER.debug(
        f"{config_entry.title} version: {config_entry.version}.{config_entry.minor_version}")
    if config_entry.version == 2 and config_entry.data["provider"] == "Event Calendar":
        _LOGGER.info(
            "Migrating LLM Vision Timeline config entry from v2.0 to v3.0")
        # Change Provider name to Timeline
        new_data = config_entry.data.copy()
        new_data["provider"] = "Timeline"

        # Update the config entry
        hass.config_entries.async_update_entry(
            config_entry, title="LLM Vision Timeline", data=new_data, version=3, minor_version=0
        )
        return True
    else:
        hass.config_entries.async_update_entry(
            config_entry, version=3, minor_version=0
        )
        return True


async def _remember(hass, call, start, response, key_frame) -> None:
    if call.remember:
        # Find timeline config
        config_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            # Check if the config entry is empty
            if entry.data["provider"] == "Timeline":
                config_entry = entry
                break

        if config_entry is None:
            raise ServiceValidationError(
                f"Config entry not found. Please create the 'Timeline' config entry first.")

        timeline = Timeline(hass, config_entry)

        if call.image_entities and len(call.image_entities) > 0:
            camera_name = call.image_entities[0]
        elif call.video_paths and len(call.video_paths) > 0:
            camera_name = call.video_paths[0].split(
                "/")[-1].replace(".mp4", "")
        else:
            camera_name = ""

        if "title" in response:
            title = response.get("title")
        else:
            title = "Motion detected"

        await timeline.remember(
            start=start,
            end=dt_util.now() + timedelta(minutes=1),
            label=title,
            summary=response["response_text"],
            key_frame=key_frame,
            camera_name=camera_name
        )


async def _update_sensor(hass, sensor_entity: str, value: str | int, type: str) -> None:
    """Update the value of a sensor entity."""
    # Attempt to parse the response
    value = value.strip()
    if type == "boolean":
        if value.lower() in ["on", "off"]:
            new_value = value
        else:
            value_lower = value.lower()
            if value_lower in ["true", "false"]:
                new_value = "on" if value_lower == "true" else "off"
            elif re.match(r"^\s*yes\s*[,]*", value_lower):
                new_value = "on"
            elif re.match(r"^\s*no\s*[,]*", value_lower):
                new_value = "off"
            else:
                raise ServiceValidationError(
                    f"Response {value} could not be parsed. Please check your prompt.")

    elif type == "number":
        try:
            new_value = float(value)
        except ValueError:
            raise ServiceValidationError(
                f"Response {value} could not be parsed. Please check your prompt.")

    elif type == "option":
        options = hass.states.get(sensor_entity).attributes["options"]
        if value not in options:
            # check if .title() is in options
            if value.title() in options:
                new_value = value.title()
            else:
                raise ServiceValidationError(
                    f"Response {value} could not be parsed. Please check your prompt.")
        else:
            new_value = value

    elif type == "text":
        new_value = value

    else:
        raise ServiceValidationError("Unsupported sensor entity type")

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
        self.message = str(data_call.data.get(MESSAGE, "")[0:2000])
        self.remember = data_call.data.get(REMEMBER, False)
        self.use_memory = data_call.data.get(USE_MEMORY, False)
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
        self.generate_title = data_call.data.get(GENERATE_TITLE, False)
        self.sensor_entity = data_call.data.get(SENSOR_ENTITY, "")

        # ------------ Remember ------------
        self.title = data_call.data.get("title")
        self.summary = data_call.data.get("summary")
        self.image_path = data_call.data.get("image_path", "")
        self.camera_entity = data_call.data.get("camera_entity", "")
        self.start_time = data_call.data.get("start_time", dt_util.now())
        self.end_time = data_call.data.get(
            "end_time", self.start_time + timedelta(minutes=1))

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
                                             expose_images=call.expose_images,
                                             )

        call.memory = Memory(hass)
        await call.memory._update_memory()

        # Validate configuration, input data and make the call
        response = await request.call(call)
        # Add processor.key_frame to response if it exists
        if processor.key_frame:
            response["key_frame"] = processor.key_frame

        await _remember(hass=hass,
                        call=call,
                        start=start,
                        response=response,
                        key_frame=processor.key_frame)
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
                                             frigate_retry_attempts=call.frigate_retry_attempts,
                                             frigate_retry_seconds=call.frigate_retry_seconds
                                             )
        call.memory = Memory(hass)
        await call.memory._update_memory()

        response = await request.call(call)
        # Add processor.key_frame to response if it exists
        if processor.key_frame:
            response["key_frame"] = processor.key_frame

        await _remember(hass=hass,
                        call=call,
                        start=start,
                        response=response,
                        key_frame=processor.key_frame)
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
                                              expose_images=call.expose_images,
                                              )

        call.memory = Memory(hass)
        await call.memory._update_memory()

        response = await request.call(call)
        # Add processor.key_frame to response if it exists
        if processor.key_frame:
            response["key_frame"] = processor.key_frame

        await _remember(hass=hass,
                        call=call,
                        start=start,
                        response=response,
                        key_frame=processor.key_frame)
        return response

    async def data_analyzer(data_call):
        """Handle the service call to analyze visual data"""
        start = dt_util.now()
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

        if sensor_type == "input_boolean" or sensor_type == "boolean" or sensor_type == "binary_sensor" or sensor_type == "switch":
            data_type = "one of: ['on', 'off']"
            type = "boolean"
        elif sensor_type == "input_number" or sensor_type == "number" or sensor_type == "sensor":
            data_type = "a number"
            type = "number"
        elif sensor_type == "input_select" or sensor_type == "select":
            options = hass.states.get(sensor_entity).attributes["options"]
            data_type = "one of these options: " + \
                ", ".join([f"'{option}'" for option in options])
            type = "option"
        elif sensor_type == "input_text" or sensor_type == "text":
            data_type = "text (string)"
            type = "text"
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
                                                  include_filename=call.include_filename,
                                                  expose_images=call.expose_images,
                                                  )

        call.memory = Memory(hass, system_prompt=DATA_EXTRACTION_PROMPT)
        await call.memory._update_memory()

        response = await request.call(call)
        # Add processor.key_frame to response if it exists
        if processor.key_frame:
            response["key_frame"] = processor.key_frame

        await _remember(hass=hass,
                        call=call,
                        start=start,
                        response=response,
                        key_frame=processor.key_frame)

        _LOGGER.info(f"Response: {response}")
        _LOGGER.info(f"Sensor type: {type}")
        await _update_sensor(hass, sensor_entity, response["response_text"], type)
        return response

    async def remember(data_call):
        """Handle the service call to remember an event"""
        start = dt_util.now()
        call = ServiceCallData(data_call).get_service_call_data()

        # Find timeline config
        config_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            # Check if the config entry is empty
            if entry.data["provider"] == "Timeline":
                config_entry = entry
                break

        if config_entry is None:
            raise ServiceValidationError(
                f"Config entry not found. Please create the 'Timeline' config entry first.")

        timeline = Timeline(hass, config_entry)

        await timeline.remember(
            start=call.start_time,
            end=call.end_time,
            label=call.title,
            summary=call.summary,
            key_frame=call.image_path,
            camera_name=call.camera_entity
        )

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
        supports_response=SupportsResponse.ONLY
    )
    hass.services.register(
        DOMAIN, "remember", remember,
    )

    return True
