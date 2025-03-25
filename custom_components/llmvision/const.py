""" Constants for llmvision component"""

# Global constants
DOMAIN = "llmvision"

# CONFIGURABLE VARIABLES FOR SETUP
CONF_PROVIDER = 'conf_provider'
CONF_API_KEY = 'api_key'
CONF_IP_ADDRESS= 'ip_address'
CONF_PORT = 'port'
CONF_HTTPS = 'https'
CONF_DEFAULT_MODEL = 'default_model'
CONF_TEMPERATURE = 'temperature'
CONF_TOP_P = 'top_p'

# Azure specific
CONF_AZURE_BASE_URL = 'azure_base_url'
CONF_AZURE_DEPLOYMENT = 'azure_deployment'
CONF_AZURE_VERSION = 'azure_version'

# AWS specific
CONF_AWS_ACCESS_KEY_ID = 'aws_access_key_id'
CONF_AWS_SECRET_ACCESS_KEY = 'aws_secret_access_key'
CONF_AWS_REGION_NAME = 'aws_region_name'

# Custom OpenAI specific
CONF_CUSTOM_OPENAI_ENDPOINT = 'custom_openai_endpoint'

# Timeline
CONF_RETENTION_TIME = 'retention_time'

# Memory
CONF_MEMORY_PATHS = 'memory_paths'
CONG_MEMORY_IMAGES_ENCODED = 'memory_images_encoded'
CONF_MEMORY_STRINGS = 'memory_strings'
CONF_SYSTEM_PROMPT = 'system_prompt'
CONF_TITLE_PROMPT = 'title_prompt'


# SERVICE CALL CONSTANTS
MESSAGE = 'message'
REMEMBER = 'remember'
USE_MEMORY = 'use_memory'
PROVIDER = 'provider'
MAXTOKENS = 'max_tokens'
TARGET_WIDTH = 'target_width'
MODEL = 'model'
IMAGE_FILE = 'image_file'
IMAGE_ENTITY = 'image_entity'
VIDEO_FILE = 'video_file'
EVENT_ID = 'event_id'
INTERVAL = 'interval'
DURATION = 'duration'
FRIGATE_RETRY_ATTEMPTS = 'frigate_retry_attempts'
FRIGATE_RETRY_SECONDS = 'frigate_retry_seconds'
MAX_FRAMES = 'max_frames'
INCLUDE_FILENAME = 'include_filename'
EXPOSE_IMAGES = 'expose_images'
GENERATE_TITLE = 'generate_title'
SENSOR_ENTITY = 'sensor_entity'

# Error messages
ERROR_NOT_CONFIGURED = "{provider} is not configured"
ERROR_GROQ_MULTIPLE_IMAGES = "Groq does not support videos or streams"
ERROR_NO_IMAGE_INPUT = "No image input provided"
ERROR_HANDSHAKE_FAILED = "Connection could not be established"

# Versions
# https://docs.anthropic.com/en/api/versioning
VERSION_ANTHROPIC = "2023-06-01"

# DEFAULTS
# Prompts
DEFAULT_SYSTEM_PROMPT = "Your task is to analyze a series of images and provide a concise event description based on user instructions. Focus on identifying and describing the actions of people and dynamic objects (e.g., vehicles) rather than static background details. When multiple images are provided, track and summarize movements or changes over time (e.g., 'A person walks to the front door' or 'A car pulls out of the driveway'). Keep responses brief, objective, and aligned with the user's prompt. Avoid speculation and prioritize observable activity."
DEFAULT_TITLE_PROMPT = "Provide a short and concise event title based on the description provided. The title should summarize the key actions or events captured in the images and be suitable for use in a notification or alert. Keep the title clear, relevant to the content of the images and shorter than 6 words. Avoid unnecessary details or subjective interpretations. The title should be in the format: '<Object> seen at <location>. For example: 'Person seen at front door'."
DATA_EXTRACTION_PROMPT = "You are an advanced image analysis assistant specializing in extracting precise data from images captured by a home security camera. Your task is to analyze one or more images and extract specific information as requested by the user (e.g., the number of cars or a license plate). Provide only the requested information in your response, with no additional text or commentary. Your response must be a {data_format} Ensure the extracted data is accurate and reflects the content of the images."

# Models
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
DEFAULT_AZURE_MODEL = "gpt-4o-mini"
DEFAULT_GOOGLE_MODEL = "gemini-2.0-flash"
DEFAULT_GROQ_MODEL = "llama-3.2-11b-vision-preview"
DEFAULT_LOCALAI_MODEL = "llava"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_CUSTOM_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_AWS_MODEL = "us.amazon.nova-pro-v1:0"
DEFAULT_OPENWEBUI_MODEL = "gemma3:4b"


# API Endpoints
ENDPOINT_OPENAI = "https://api.openai.com/v1/chat/completions"
ENDPOINT_ANTHROPIC = "https://api.anthropic.com/v1/messages"
ENDPOINT_GOOGLE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
ENDPOINT_GROQ = "https://api.groq.com/openai/v1/chat/completions"
ENDPOINT_LOCALAI = "{protocol}://{ip_address}:{port}/v1/chat/completions"
ENDPOINT_OLLAMA = "{protocol}://{ip_address}:{port}/api/chat"
ENDPOINT_OPENWEBUI = "{protocol}://{ip_address}:{port}/api/chat/completions"
ENDPOINT_AZURE = "{base_url}openai/deployments/{deployment}/chat/completions?api-version={api_version}"
