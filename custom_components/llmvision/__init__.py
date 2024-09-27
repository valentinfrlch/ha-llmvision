# Declare variables
from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
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
    MODEL,
    PROVIDER,
    MAXTOKENS,
    TARGET_WIDTH,
    MESSAGE,
    IMAGE_FILE,
    IMAGE_ENTITY,
    VIDEO_FILE,
    EVENT_ID,
    INTERVAL,
    TEMPERATURE,
    DETAIL,
    INCLUDE_FILENAME
)
from .request_handlers import RequestHandler
from .media_handlers import MediaProcessor
from homeassistant.core import SupportsResponse

async def async_setup_entry(hass, entry):
    """Save config entry to hass.data"""
    # Get all entries from config flow
    openai_api_key = entry.data.get(CONF_OPENAI_API_KEY)
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
            CONF_GROQ_API_KEY: groq_api_key,
            CONF_LOCALAI_IP_ADDRESS: localai_ip_address,
            CONF_LOCALAI_PORT: localai_port,
            CONF_LOCALAI_HTTPS: localai_https,
            CONF_OLLAMA_IP_ADDRESS: ollama_ip_address,
            CONF_OLLAMA_PORT: ollama_port,
            CONF_OLLAMA_HTTPS: ollama_https,
            CONF_CUSTOM_OPENAI_ENDPOINT: custom_openai_endpoint,
            CONF_CUSTOM_OPENAI_API_KEY: custom_openai_api_key
        }.items()
        if value is not None
    })

    return True


class ServiceCallData:
    """Store service call data and set default values"""
    def __init__(self, data_call):
        self.provider = str(data_call.data.get(PROVIDER))
        self.model = str(data_call.data.get(MODEL, self._default_model(self.provider)))
        self.message = str(data_call.data.get(MESSAGE)[0:2000])
        self.image_paths = data_call.data.get(IMAGE_FILE, "").split(
            "\n") if data_call.data.get(IMAGE_FILE) else None
        self.image_entities = data_call.data.get(IMAGE_ENTITY)
        self.video_paths = data_call.data.get(VIDEO_FILE, "").split(
            "\n") if data_call.data.get(VIDEO_FILE) else None
        self.event_id = data_call.data.get(EVENT_ID, "").split(
            "\n") if data_call.data.get(EVENT_ID) else None
        self.interval = int(data_call.data.get(INTERVAL, 3))
        self.target_width = data_call.data.get(TARGET_WIDTH, 1280)
        self.temperature = float(data_call.data.get(TEMPERATURE, 0.5))
        self.max_tokens = int(data_call.data.get(MAXTOKENS, 100))
        self.detail = str(data_call.data.get(DETAIL, "auto"))
        self.include_filename = data_call.data.get(INCLUDE_FILENAME, False)

    def get_service_call_data(self):
        return self
    
    def _default_model(self, provider):
        if provider == "OpenAI":
            return "gpt-4o-mini"
        elif provider == "Anthropic":
            return "claude-3-5-sonnet-20240620"
        elif provider == "Google":
            return "gemini-1.5-flash-latest"
        elif provider == "Groq":
            return "llava-v1.5-7b-4096-preview"
        elif provider == "LocalAI":
            return "gpt-4-vision-preview"
        elif provider == "Ollama":
            return "llava-phi3:latest"
        elif provider == "Custom OpenAI":
            return "gpt-4o-mini"


def setup(hass, config):
    async def image_analyzer(data_call):
        """Handle the service call to analyze an image with LLM Vision"""
        
        # Initialize call objecto with service call data
        call = ServiceCallData(data_call).get_service_call_data()
        # Initialize the RequestHandler client
        client = RequestHandler(hass,
                                message=call.message,
                                max_tokens=call.max_tokens,
                                temperature=call.temperature,
                                detail=call.detail)

        # Fetch and preprocess images
        processor = MediaProcessor(hass, client)
        # Send images to RequestHandler client
        client = await processor.add_images(call.image_entities, call.image_paths, call.target_width, call.include_filename)

        # Validate configuration, input data and make the call
        response = await client.make_request(call)
        return response

    async def video_analyzer(data_call):
        """Handle the service call to analyze a video (future implementation)"""
        call = ServiceCallData(data_call).get_service_call_data()
        call.message = "The attached images are frames from a video. " + call.message
        client = RequestHandler(hass,
                                message=call.message,
                                max_tokens=call.max_tokens,
                                temperature=call.temperature,
                                detail=call.detail)
        processor = MediaProcessor(hass, client)
        client = await processor.add_videos(call.video_paths, call.event_id, call.interval, call.target_width, call.include_filename)
        response = await client.make_request(call)
        return response

    hass.services.register(
        DOMAIN, "image_analyzer", image_analyzer,
        supports_response=SupportsResponse.ONLY
    )
    hass.services.register(
        DOMAIN, "video_analyzer", video_analyzer,
        supports_response=SupportsResponse.ONLY
    )

    return True
 