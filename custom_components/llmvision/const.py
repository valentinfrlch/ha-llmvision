"""Constants for llmvision component"""

# Global constants
DOMAIN = "llmvision"

# CONFIGURABLE VARIABLES FOR SETUP
CONF_PROVIDER = "provider"
CONF_API_KEY = "api_key"
CONF_IP_ADDRESS = "ip_address"
CONF_PORT = "port"
CONF_HTTPS = "https"
CONF_DEFAULT_MODEL = "default_model"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_THINKING_BUDGET = "thinking_budget"
CONF_THINK = "think"
CONF_REASONING_EFFORT = "reasoning_effort"
CONF_CONTEXT_WINDOW = "context_window"  # (ollama: num_ctx)
CONF_KEEP_ALIVE = "keep_alive"
CONF_REQUEST_TIMEOUT = "request_timeout"

# Azure specific
CONF_AZURE_BASE_URL = "azure_base_url"
CONF_AZURE_DEPLOYMENT = "azure_deployment"
CONF_AZURE_VERSION = "azure_version"

# AWS specific
CONF_AWS_ACCESS_KEY_ID = "aws_access_key_id"
CONF_AWS_SECRET_ACCESS_KEY = "aws_secret_access_key"
CONF_AWS_REGION_NAME = "aws_region_name"

# Custom OpenAI specific
CONF_CUSTOM_OPENAI_ENDPOINT = "custom_openai_endpoint"

# Timeline
CONF_RETENTION_TIME = "retention_time"

# Settings
CONF_TIMELINE_LANGUAGE = "timeline_language"
CONF_FALLBACK_PROVIDER = "fallback_provider"
CONF_TIMELINE_TODAY_SUMMARY = "timeline_today_summary"
CONF_TIMELINE_SUMMARY_PROMPT = "timeline_summary_prompt"
CONF_MEMORY_PATHS = "memory_paths"
CONF_MEMORY_IMAGES_ENCODED = "memory_images_encoded"
CONF_MEMORY_STRINGS = "memory_strings"
CONF_SYSTEM_PROMPT = "system_prompt"
CONF_TITLE_PROMPT = "title_prompt"
CONF_MEMORY_PATHS = "memory_paths"
CONF_MEMORY_IMAGES_ENCODED = "memory_images_encoded"
CONF_MEMORY_STRINGS = "memory_strings"

# Dispatcher signals
SIGNAL_TIMELINE_UPDATED = f"{DOMAIN}_timeline_updated"


# SERVICE CALL CONSTANTS
MESSAGE = "message"
STORE_IN_TIMELINE = "store_in_timeline"
USE_MEMORY = "use_memory"
PROVIDER = "provider"
MAXTOKENS = "max_tokens"
TARGET_WIDTH = "target_width"
MODEL = "model"
IMAGE_FILE = "image_file"
IMAGE_ENTITY = "image_entity"
VIDEO_FILE = "video_file"
EVENT_ID = "event_id"
INTERVAL = "interval"
DURATION = "duration"
FRIGATE_RETRY_ATTEMPTS = "frigate_retry_attempts"
FRIGATE_RETRY_SECONDS = "frigate_retry_seconds"
MAX_FRAMES = "max_frames"
RESPONSE_FORMAT = "response_format"
STRUCTURE = "structure"
TITLE_FIELD = "title_field"
DESCRIPTION_FIELD = "description_field"
DESCPRIPTION_FIELD = DESCRIPTION_FIELD  # Deprecated: kept for backward compatibility
INCLUDE_FILENAME = "include_filename"
EXPOSE_IMAGES = "expose_images"
GENERATE_TITLE = "generate_title"
SENSOR_ENTITY = "sensor_entity"

# Error messages
ERROR_NOT_CONFIGURED = "{provider} is not configured"
ERROR_GROQ_MULTIPLE_IMAGES = "Groq does not support videos or streams"
ERROR_NO_IMAGE_INPUT = "No image input provided"
ERROR_HANDSHAKE_FAILED = "Connection could not be established"

# Versions
VERSION_ANTHROPIC = "2023-06-01"  # https://docs.anthropic.com/en/api/versioning
VERSION_AZURE = "2025-04-01-preview"  # https://learn.microsoft.com/en-us/azure/ai-foundry/openai/api-version-lifecycle?tabs=key

# Defaults
DEFAULT_SYSTEM_PROMPT = "Analyze the images and give a concise, objective event summary (<255 chars). Focus on people, pets, and moving objects; track changes across images. Exclude static details, avoid speculation, and follow user instructions."
DEFAULT_TITLE_PROMPT = "Generate a clear event title (<6 words) from the description. Use format: <Object> seen at <location>. Keep it concise, factual, and alert-ready. Include names if given. Avoid extra details or interpretations."
DATA_EXTRACTION_PROMPT = "Analyze the image(s) and extract only the requested info (e.g., object count, license plate). Output strictly in {data_format}. Double-check accuracy and ensure results reflect the image content. Do not explain or add extra info."
GLIMPSE_V1_INSTRUCTIONS = """Task: Analyze the provided security camera image and generate a smart-home event notification.

Output:
Return a single valid JSON object with exactly two string fields:
- "title": a short summary (2-5 words)
- "description": a brief factual description of what is happening

Title Rules:
The "title" must:
- Be 2-5 words
- Be short and glanceable
- Avoid long phrases or full sentences
The title should summarize the event category and location.
All additional detail belongs in "description".

Delivery Inference Rules:
If a person is:
- Holding or placing a package or letters
- and wearing a delivery uniform
- or a delivery vehicle is visible
Then:
- the title must contain the word "delivery":
  - Use a delivery-style title (2-5 words) (examples: "Package delivery", "Delivery at porch", "Courier delivery")
  - Include the carrier name in the description if the carrier branding is visually identifiable (e.g. "Amazon delivery", "FedEx delivery")

Empty scene handling:
- If no clear activity or relevant objects (such as people, vehicles, or animals) are present, set:
  - "title" to exactly: "No activity"
  - "description" to a brief statement describing that nothing notable is seen

Description Rules:
- 1-2 short sentences
- Do not include explanations or reasoning
- Do not repeat the task or rules
- Use present tense
- Neutral and factual
- Describe what is happening

Do not mention camera angle, lighting quality, or image clarity.
"""
# Models
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"
DEFAULT_AZURE_MODEL = "gpt-4o-mini"
DEFAULT_GOOGLE_MODEL = "gemini-3.1-flash-lite"
DEFAULT_GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
DEFAULT_LOCALAI_MODEL = "llava"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_CUSTOM_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_AWS_MODEL = "us.amazon.nova-pro-v1:0"
DEFAULT_OPENWEBUI_MODEL = "gemma3:4b"
DEFAULT_OPENROUTER_MODEL = "google/gemma-3-4b-it:free"

DEFAULT_SUMMARY_PROMPT = "Provide a brief summary for the following titles. Focus on the key actions or changes that occurred over time and avoid unnecessary details or subjective interpretations. The summary should be concise, objective, and relevant to the content of the images. Keep the summary under 50 words and ensure it captures the main events or activities described in the descriptions. Here are the descriptions:\n "

# API Endpoints
ENDPOINT_OPENAI = "https://api.openai.com/v1/chat/completions"
ENDPOINT_ANTHROPIC = "https://api.anthropic.com/v1/messages"
ENDPOINT_GOOGLE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
ENDPOINT_GROQ = "https://api.groq.com/openai/v1/chat/completions"
ENDPOINT_LOCALAI = "{protocol}://{ip_address}:{port}/v1/chat/completions"
ENDPOINT_OLLAMA = "{protocol}://{ip_address}:{port}/api/chat"
ENDPOINT_OPENWEBUI = "{protocol}://{ip_address}:{port}/api/chat/completions"
ENDPOINT_AZURE = "{base_url}openai/deployments/{deployment}/chat/completions?api-version={api_version}"
ENDPOINT_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
