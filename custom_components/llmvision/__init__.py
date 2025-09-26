from datetime import datetime
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

# Declare variables
from .const import (
    DOMAIN,
    CONF_PROVIDER,
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_HTTPS,
    CONF_DEFAULT_MODEL,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_AZURE_VERSION,
    CONF_AZURE_BASE_URL,
    CONF_AZURE_DEPLOYMENT,
    CONF_CUSTOM_OPENAI_ENDPOINT,
    CONF_RETENTION_TIME,
    CONF_MEMORY_PATHS,
    CONF_MEMORY_IMAGES_ENCODED,
    CONF_MEMORY_STRINGS,
    CONF_SYSTEM_PROMPT,
    CONF_TITLE_PROMPT,
    CONF_AWS_ACCESS_KEY_ID,
    CONF_AWS_SECRET_ACCESS_KEY,
    CONF_AWS_REGION_NAME,
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
    INTERVAL,
    DURATION,
    MAX_FRAMES,
    INCLUDE_FILENAME,
    EXPOSE_IMAGES,
    GENERATE_TITLE,
    SENSOR_ENTITY,
    DATA_EXTRACTION_PROMPT,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_AZURE_MODEL,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_LOCALAI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_CUSTOM_OPENAI_MODEL,
    DEFAULT_AWS_MODEL,
    DEFAULT_OPENWEBUI_MODEL,
    CONF_CONTEXT_WINDOW,
    CONF_KEEP_ALIVE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Save config entry to hass.data in a standardized way (generic keys, by entry_uid)."""
    entry_uid = entry.entry_id

    # Build a standardized config dict with only generic keys
    provider_config = {
        CONF_PROVIDER: entry.data.get(CONF_PROVIDER),
        CONF_API_KEY: entry.data.get(CONF_API_KEY),
        CONF_IP_ADDRESS: entry.data.get(CONF_IP_ADDRESS),
        CONF_PORT: entry.data.get(CONF_PORT),
        CONF_HTTPS: entry.data.get(CONF_HTTPS),
        CONF_DEFAULT_MODEL: entry.data.get(CONF_DEFAULT_MODEL),
        CONF_TEMPERATURE: entry.data.get(CONF_TEMPERATURE),
        CONF_TOP_P: entry.data.get(CONF_TOP_P),
        # Ollama specific
        CONF_CONTEXT_WINDOW: entry.data.get(CONF_CONTEXT_WINDOW),
        CONF_KEEP_ALIVE: entry.data.get(CONF_KEEP_ALIVE),
        # Azure specific
        CONF_AZURE_BASE_URL: entry.data.get(CONF_AZURE_BASE_URL),
        CONF_AZURE_DEPLOYMENT: entry.data.get(CONF_AZURE_DEPLOYMENT),
        CONF_AZURE_VERSION: entry.data.get(CONF_AZURE_VERSION),
        # Custom OpenAI specific
        CONF_CUSTOM_OPENAI_ENDPOINT: entry.data.get(CONF_CUSTOM_OPENAI_ENDPOINT),
        # AWS specific
        CONF_AWS_ACCESS_KEY_ID: entry.data.get(CONF_AWS_ACCESS_KEY_ID),
        CONF_AWS_SECRET_ACCESS_KEY: entry.data.get(CONF_AWS_SECRET_ACCESS_KEY),
        CONF_AWS_REGION_NAME: entry.data.get(CONF_AWS_REGION_NAME),
        # Settings
        CONF_RETENTION_TIME: entry.data.get(CONF_RETENTION_TIME),
        CONF_MEMORY_PATHS: entry.data.get(CONF_MEMORY_PATHS),
        CONF_MEMORY_IMAGES_ENCODED: entry.data.get(CONF_MEMORY_IMAGES_ENCODED),
        CONF_MEMORY_STRINGS: entry.data.get(CONF_MEMORY_STRINGS),
        CONF_SYSTEM_PROMPT: entry.data.get(CONF_SYSTEM_PROMPT),
        CONF_TITLE_PROMPT: entry.data.get(CONF_TITLE_PROMPT),
    }

    # Filter out None values
    filtered_provider_config = {
        key: value for key, value in provider_config.items() if value is not None
    }

    # Ensure DOMAIN exists in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Store the filtered config under the entry_uid (subdict per entry)
    hass.data[DOMAIN][entry_uid] = filtered_provider_config

    # If this is the Settings entry, set up the calendar and run cleanup
    if filtered_provider_config.get(CONF_PROVIDER) == "Settings":
        await hass.config_entries.async_forward_entry_setups(entry, ["calendar"])
        timeline = Timeline(hass, entry)
        await timeline._cleanup()

    # Sanitize provider config (remove api_key and value)
    sanitized_provider_config = {
        key: value
        for key, value in filtered_provider_config.items()
        if key != CONF_API_KEY
    }

    # Print the config entry data for debugging
    _LOGGER.debug(f"Config entry {entry.title} data: {sanitized_provider_config}")
    return True


async def async_remove_entry(hass, entry):
    """Remove config entry from hass.data"""
    entry_uid = entry.entry_id
    if DOMAIN in hass.data and entry_uid in hass.data[DOMAIN]:
        _LOGGER.info(f"Removing {entry.title} from hass.data")
        await async_unload_entry(hass, entry)
        hass.data[DOMAIN].pop(entry_uid)
        if entry.data[CONF_PROVIDER] == "Settings":
            db_path = os.path.join(hass.config.path("llmvision"), "events.db")
            if os.path.exists(db_path):
                os.remove(db_path)
    else:
        _LOGGER.warning(
            f"Entry {entry.title} not found but was requested to be removed"
        )
    return True


async def async_unload_entry(hass, entry) -> bool:
    _LOGGER.debug(f"Unloading {entry.title} from hass.data")
    # check if the entry is the calendar entry (has entry rentention_time)
    if entry.data.get(CONF_RETENTION_TIME) is not None:
        # unload the calendar
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, ["calendar"]
        )
    else:
        unload_ok = True
    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry) -> bool:
    _LOGGER.debug(
        f"{config_entry.title} provider v{config_entry.version}.{config_entry.minor_version}"
    )

    new_data = config_entry.data.copy()
    updated = False

    # v2 -> v3: Rename "Event Calendar" to "Timeline"
    if config_entry.version == 2 and new_data.get(CONF_PROVIDER) == "Event Calendar":
        new_data[CONF_PROVIDER] = "Timeline"
        hass.config_entries.async_update_entry(
            config_entry,
            title="LLM Vision Timeline",
            data=new_data,
            version=3,
            minor_version=0,
        )

    # v3 -> v4: Standardize keys for all providers, Memory, Timeline merge into Settings
    if config_entry.version == 3:
        provider = new_data.get(PROVIDER) or new_data.get(CONF_PROVIDER)
        # Example for OpenAI, add similar logic for other providers if needed
        if provider == "Timeline":
            retention_time = config_entry.data.get(CONF_RETENTION_TIME, 7)
            # Find the Memory entry
            target_entry = None
            for entry in hass.config_entries.async_entries(DOMAIN):
                if entry.data.get(CONF_PROVIDER) == "Memory":
                    target_entry = entry
                    break
            if target_entry:
                # Migrate retention_time to this entry
                new_data = dict(target_entry.data)
                new_data[CONF_RETENTION_TIME] = retention_time
                hass.config_entries.async_update_entry(target_entry, data=new_data)
            # Log hass.data[DOMAIN] for debugging
            _LOGGER.debug(f"hass.data[DOMAIN]: {hass.data.get(DOMAIN, {})}")
            # Remove the Timeline entry
            _LOGGER.info(
                f"Scheduling removal of old Timeline config entry {config_entry.title}"
            )
            hass.async_create_task(
                hass.config_entries.async_remove(config_entry.entry_id)
            )
        if provider == "Memory":
            # Change the provider name to "Settings"
            new_data[CONF_PROVIDER] = "Settings"
            # Update the title to "LLM Vision Settings"
            hass.config_entries.async_update_entry(
                config_entry,
                title="LLM Vision Settings",
                data=new_data,
                version=4,
                minor_version=0,
            )
        if provider == "OpenAI":
            # Migrate old provider-specific keys to generic keys
            if "openai_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("openai_api_key")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_OPENAI_MODEL
                updated = True
            if "openai_temperature" not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if "openai_top_p" in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        if provider == "Anthropic":
            if "anthropic_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("anthropic_api_key")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_ANTHROPIC_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        # Azure
        if provider == "Azure":
            if "azure_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("azure_api_key")
                updated = True
            if "azure_base_url" in new_data:
                new_data[CONF_AZURE_BASE_URL] = new_data.pop("azure_base_url")
                updated = True
            if "azure_deployment" in new_data:
                new_data[CONF_AZURE_DEPLOYMENT] = new_data.pop("azure_deployment")
                updated = True
            if "azure_version" in new_data:
                new_data[CONF_AZURE_VERSION] = new_data.pop("azure_version")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_AZURE_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        # Groq
        if provider == "Groq":
            if "groq_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("groq_api_key")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_GROQ_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        # Google
        if provider == "Google":
            if "google_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("google_api_key")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_GOOGLE_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        # LocalAI
        if provider == "LocalAI":
            if "localai_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("localai_api_key")
                updated = True
            if "localai_ip_address" in new_data:
                new_data[CONF_IP_ADDRESS] = new_data.pop("localai_ip_address")
                updated = True
            if "localai_port" in new_data:
                new_data[CONF_PORT] = new_data.pop("localai_port")
                updated = True
            if "localai_https" in new_data:
                new_data[CONF_HTTPS] = new_data.pop("localai_https")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_LOCALAI_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        # Ollama
        if provider == "Ollama":
            if "ollama_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("ollama_api_key")
                updated = True
            if "ollama_ip_address" in new_data:
                new_data[CONF_IP_ADDRESS] = new_data.pop("ollama_ip_address")
                updated = True
            if "ollama_port" in new_data:
                new_data[CONF_PORT] = new_data.pop("ollama_port")
                updated = True
            if "ollama_https" in new_data:
                new_data[CONF_HTTPS] = new_data.pop("ollama_https")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_OLLAMA_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        # Custom OpenAI
        if provider == "Custom OpenAI":
            if "custom_openai_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("custom_openai_api_key")
                updated = True
            if "custom_openai_endpoint" in new_data:
                new_data[CONF_CUSTOM_OPENAI_ENDPOINT] = new_data.pop(
                    "custom_openai_endpoint"
                )
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_CUSTOM_OPENAI_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        # AWS
        if provider == "AWS":
            if "aws_access_key_id" in new_data:
                new_data[CONF_AWS_ACCESS_KEY_ID] = new_data.pop("aws_access_key_id")
                updated = True
            if "aws_secret_access_key" in new_data:
                new_data[CONF_AWS_SECRET_ACCESS_KEY] = new_data.pop(
                    "aws_secret_access_key"
                )
                updated = True
            if "aws_region_name" in new_data:
                new_data[CONF_AWS_REGION_NAME] = new_data.pop("aws_region_name")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_AWS_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True
        # OpenWebUI
        if provider == "OpenWebUI":
            if "openwebui_api_key" in new_data:
                new_data[CONF_API_KEY] = new_data.pop("openwebui_api_key")
                updated = True
            if "openwebui_ip_address" in new_data:
                new_data[CONF_IP_ADDRESS] = new_data.pop("openwebui_ip_address")
                updated = True
            if "openwebui_port" in new_data:
                new_data[CONF_PORT] = new_data.pop("openwebui_port")
                updated = True
            if "openwebui_https" in new_data:
                new_data[CONF_HTTPS] = new_data.pop("openwebui_https")
                updated = True
            if CONF_DEFAULT_MODEL not in new_data:
                new_data[CONF_DEFAULT_MODEL] = DEFAULT_OPENWEBUI_MODEL
                updated = True
            if CONF_TEMPERATURE not in new_data:
                new_data[CONF_TEMPERATURE] = 0.5
                updated = True
            if CONF_TOP_P not in new_data:
                new_data[CONF_TOP_P] = 0.9
                updated = True

        if updated:
            hass.config_entries.async_update_entry(
                config_entry, data=new_data, version=4, minor_version=0
            )
            return True

    return True


async def _remember(
    hass,
    call: dict,
    start: datetime,
    response: dict,
    key_frame: str,
    today_summary: str,
) -> None:
    if call.remember:
        # Find timeline config
        config_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            # Check if the config entry is empty
            if entry.data[CONF_PROVIDER] == "Settings":
                config_entry = entry
                break

        if config_entry is None:
            raise ServiceValidationError(
                f"Settings config entry not found. Please set up LLM Vision first."
            )

        timeline = Timeline(hass, config_entry)

        if call.image_entities and len(call.image_entities) > 0:
            camera_name = call.image_entities[0]
        elif call.video_paths and len(call.video_paths) > 0:
            camera_name = call.video_paths[0].split("/")[-1].replace(".mp4", "")
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
            camera_name=camera_name,
            today_summary=today_summary,
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
                    f"Response {value} could not be parsed. Please check your prompt."
                )

    elif type == "number":
        try:
            new_value = float(value)
        except ValueError:
            raise ServiceValidationError(
                f"Response {value} could not be parsed. Please check your prompt."
            )

    elif type == "option":
        options = hass.states.get(sensor_entity).attributes["options"]
        if value not in options:
            # check if .title() is in options
            if value.title() in options:
                new_value = value.title()
            else:
                raise ServiceValidationError(
                    f"Response {value} could not be parsed. Please check your prompt."
                )
        else:
            new_value = value

    elif type == "text":
        new_value = value

    else:
        raise ServiceValidationError("Unsupported sensor entity type")

    # Update the value
    _LOGGER.info(f"Updating sensor {sensor_entity} with new value: {new_value}")
    try:
        current_attributes = hass.states.get(sensor_entity).attributes.copy()
        hass.states.async_set(sensor_entity, new_value, current_attributes)
    except Exception as e:
        _LOGGER.error(f"Failed to update sensor {sensor_entity}: {e}")
        raise


class ServiceCallData:
    """Store service call data and set default values"""

    def __init__(self, data_call):
        # This is the config entry id
        self.provider = str(data_call.data.get(PROVIDER))
        # If not set, the conf_default_model will be set in providers.py
        self.model = data_call.data.get(MODEL)
        self.message = str(data_call.data.get(MESSAGE, "")[0:2000])
        self.remember = data_call.data.get(REMEMBER, False)
        self.use_memory = data_call.data.get(USE_MEMORY, False)
        self.image_paths = (
            data_call.data.get(IMAGE_FILE, "").split("\n")
            if data_call.data.get(IMAGE_FILE)
            else None
        )
        self.image_entities = data_call.data.get(IMAGE_ENTITY)
        self.video_paths = (
            data_call.data.get(VIDEO_FILE, "").split("\n")
            if data_call.data.get(VIDEO_FILE)
            else None
        )
        self.event_id = (
            data_call.data.get(EVENT_ID, "").split("\n")
            if data_call.data.get(EVENT_ID)
            else None
        )
        self.interval = int(data_call.data.get(INTERVAL, 2))
        self.duration = int(data_call.data.get(DURATION, 10))
        self.max_frames = int(data_call.data.get(MAX_FRAMES, 3))
        self.target_width = data_call.data.get(TARGET_WIDTH, 3840)
        self.temperature = float()
        self.max_tokens = int(data_call.data.get(MAXTOKENS, 3000))
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
        self.start_time = self._convert_time_input_to_datetime(self.start_time)
        self.end_time = data_call.data.get(
            "end_time", self.start_time + timedelta(minutes=1)
        )
        self.end_time = self._convert_time_input_to_datetime(self.end_time)

        # ------------ Added during call ------------
        # self.base64_images : List[str] = []
        # self.filenames : List[str] = []

    def _convert_time_input_to_datetime(self, time_input) -> datetime:
        """Convert time input to datetime object"""

        if isinstance(time_input, datetime):
            return time_input
        if isinstance(time_input, (int, float)):
            # Assume it's a Unix timestamp (seconds since epoch)
            return datetime.fromtimestamp(time_input)
        if isinstance(time_input, str):
            # Try parsing ISO format first
            try:
                return datetime.fromisoformat(time_input)
            except ValueError:
                pass
            # Try parsing as timestamp string
            try:
                return datetime.fromtimestamp(float(time_input))
            except Exception:
                pass
            raise ValueError(f"Unsupported date string format: {time_input}")
        raise TypeError(f"Unsupported type for time_input: {type(time_input)}")

    def get_service_call_data(self):
        return self


def setup(hass, config):
    async def image_analyzer(data_call):
        """Handle the service call to analyze an image with LLM Vision"""
        start = dt_util.now()

        # Log the service call data
        _LOGGER.debug(f"Service call data: {data_call.data}")
        # Log the provider
        _LOGGER.debug(f"Provider: {data_call.data.get(PROVIDER)}")

        # Initialize call object with service call data
        call = ServiceCallData(data_call).get_service_call_data()
        # Initialize the RequestHandler client
        request = Request(
            hass=hass,
            message=call.message,
            max_tokens=call.max_tokens,
            temperature=call.temperature,
        )
        # Fetch and preprocess images
        processor = MediaProcessor(hass, request)
        # Send images to RequestHandler client
        request = await processor.add_images(
            image_entities=call.image_entities,
            image_paths=call.image_paths,
            target_width=call.target_width,
            include_filename=call.include_filename,
            expose_images=call.expose_images,
        )

        call.memory = Memory(hass)
        await call.memory._update_memory()

        # Validate configuration, input data and make the call
        response = await request.call(call)
        _LOGGER.info(f"Response: {response}")
        # Add processor.key_frame to response if it exists
        if processor.key_frame:
            _LOGGER.info(f"Key frame: {processor.key_frame}")
            response["key_frame"] = processor.key_frame

        await _remember(
            hass=hass,
            call=call,
            start=start,
            response=response,
            key_frame=processor.key_frame,
            today_summary=response.get("today_summary", ""),
        )
        return response

    async def video_analyzer(data_call):
        """Handle the service call to analyze a video (future implementation)"""
        start = dt_util.now()
        call = ServiceCallData(data_call).get_service_call_data()
        call.message = "The attached images are frames from a video. " + call.message

        request = Request(
            hass,
            message=call.message,
            max_tokens=call.max_tokens,
            temperature=call.temperature,
        )
        processor = MediaProcessor(hass, request)
        request = await processor.add_videos(
            video_paths=call.video_paths,
            event_ids=call.event_id,
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

        await _remember(
            hass=hass,
            call=call,
            start=start,
            response=response,
            key_frame=processor.key_frame,
            today_summary=response.get("today_summary", ""),
        )
        return response

    async def stream_analyzer(data_call):
        """Handle the service call to analyze a stream"""
        start = dt_util.now()
        call = ServiceCallData(data_call).get_service_call_data()
        call.message = (
            "The attached images are frames from a live camera feed. " + call.message
        )
        request = Request(
            hass,
            message=call.message,
            max_tokens=call.max_tokens,
            temperature=call.temperature,
        )
        processor = MediaProcessor(hass, request)

        request = await processor.add_streams(
            image_entities=call.image_entities,
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

        await _remember(
            hass=hass,
            call=call,
            start=start,
            response=response,
            key_frame=processor.key_frame,
            today_summary=response.get("today_summary", ""),
        )
        return response

    async def data_analyzer(data_call):
        """Handle the service call to analyze visual data"""
        start = dt_util.now()
        call = ServiceCallData(data_call).get_service_call_data()
        sensor_entity = data_call.data.get("sensor_entity")
        _LOGGER.debug(f"Sensor entity: {sensor_entity}")

        # get current value to determine data type
        state = hass.states.get(sensor_entity).state
        sensor_type = sensor_entity.split(".")[0]
        _LOGGER.debug(f"Current state: {state}")
        _LOGGER.debug(f"Sensor type: {sensor_type}")

        if state == "unavailable":
            raise ServiceValidationError("Sensor entity is unavailable")

        if (
            sensor_type == "input_boolean"
            or sensor_type == "boolean"
            or sensor_type == "binary_sensor"
            or sensor_type == "switch"
        ):
            data_type = "one of: ['on', 'off']"
            type = "boolean"
        elif (
            sensor_type == "input_number"
            or sensor_type == "number"
            or sensor_type == "sensor"
        ):
            data_type = "a number"
            type = "number"
        elif sensor_type == "input_select" or sensor_type == "select":
            options = hass.states.get(sensor_entity).attributes["options"]
            data_type = "one of these options: " + ", ".join(
                [f"'{option}'" for option in options]
            )
            type = "option"
        elif sensor_type == "input_text" or sensor_type == "text":
            data_type = "text (string)"
            type = "text"
        else:
            raise ServiceValidationError("Unsupported sensor entity type")

        call.message = (
            f"Your job is to extract data from images. You can only respond with {data_type}. You must respond with one of the options! If unsure, choose the option that best matches. Answer the following question with the options provided: "
            + call.message
        )
        request = Request(
            hass,
            message=call.message,
            max_tokens=call.max_tokens,
            temperature=call.temperature,
        )
        processor = MediaProcessor(hass, request)
        request = await processor.add_visual_data(
            image_entities=call.image_entities,
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

        await _remember(
            hass=hass,
            call=call,
            start=start,
            response=response,
            key_frame=processor.key_frame,
            today_summary=response.get("today_summary", ""),
        )

        _LOGGER.debug(f"Response: {response}")
        _LOGGER.debug(f"Sensor type: {type}")
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
            if entry.data[CONF_PROVIDER] == "Settings":
                config_entry = entry
                break

        if config_entry is None:
            raise ServiceValidationError(
                f"Config entry not found. Please create the 'Settings' config entry first."
            )

        timeline = Timeline(hass, config_entry)

        await timeline.remember(
            start=call.start_time,
            end=call.end_time,
            label=call.title,
            summary=call.summary,
            key_frame=call.image_path,
            camera_name=call.camera_entity,
        )

    # Register actions
    hass.services.register(
        DOMAIN,
        "image_analyzer",
        image_analyzer,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.register(
        DOMAIN,
        "video_analyzer",
        video_analyzer,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.register(
        DOMAIN,
        "stream_analyzer",
        stream_analyzer,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.register(
        DOMAIN, "data_analyzer", data_analyzer, supports_response=SupportsResponse.ONLY
    )
    hass.services.register(
        DOMAIN,
        "remember",
        remember,
    )

    return True
