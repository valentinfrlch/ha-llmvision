from homeassistant import config_entries
from homeassistant.helpers.selector import selector
from homeassistant.exceptions import ServiceValidationError
from .providers import (
    OpenAI,
    AzureOpenAI,
    Anthropic,
    Google,
    Groq,
    LocalAI,
    Ollama,
)
from .const import (
    DOMAIN,
    CONF_OPENAI_API_KEY,
    CONF_AZURE_API_KEY,
    CONF_AZURE_BASE_URL,
    CONF_AZURE_DEPLOYMENT,
    CONF_AZURE_VERSION,
    ENDPOINT_AZURE,
    CONF_ANTHROPIC_API_KEY,
    CONF_GOOGLE_API_KEY,
    CONF_GROQ_API_KEY,
    CONF_LOCALAI_IP_ADDRESS,
    CONF_LOCALAI_PORT,
    CONF_LOCALAI_HTTPS,
    CONF_OLLAMA_IP_ADDRESS,
    CONF_OLLAMA_PORT,
    CONF_OLLAMA_HTTPS,
    CONF_CUSTOM_OPENAI_API_KEY,
    CONF_CUSTOM_OPENAI_ENDPOINT,
    CONF_RETENTION_TIME,
)
import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)


class llmvisionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 2

    async def handle_provider(self, provider):
        provider_steps = {
            "Anthropic": self.async_step_anthropic,
            "Azure": self.async_step_azure,
            "Custom OpenAI": self.async_step_custom_openai,
            "Event Calendar": self.async_step_semantic_index,
            "Google": self.async_step_google,
            "Groq": self.async_step_groq,
            "LocalAI": self.async_step_localai,
            "Ollama": self.async_step_ollama,
            "OpenAI": self.async_step_openai,
        }

        step_method = provider_steps.get(provider)
        if step_method:
            return await step_method()
        else:
            _LOGGER.error(f"Unknown provider: {provider}")
            return self.async_abort(reason="unknown_provider")

    async def async_step_user(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required("provider", default="Event Calendar"): selector({
                "select": {
                    "options": ["Anthropic", "Google", "Groq", "LocalAI", "Ollama", "OpenAI", "Custom OpenAI", "Event Calendar"], # Azure removed until fixed
                    "mode": "dropdown",
                    "sort": False,
                    "custom_value": False
                }
            }),
        })

        if user_input is not None:
            self.init_info = user_input
            provider = user_input["provider"]
            return await self.handle_provider(provider)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders=user_input
        )

    async def async_step_localai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_LOCALAI_IP_ADDRESS): str,
            vol.Required(CONF_LOCALAI_PORT, default=8080): int,
            vol.Required(CONF_LOCALAI_HTTPS, default=False): bool,
        })

        if user_input is not None:
            # save provider to user_input
            user_input["provider"] = self.init_info["provider"]
            try:
                localai = LocalAI(self.hass, endpoint={
                    'ip_address': user_input[CONF_LOCALAI_IP_ADDRESS],
                    'port': user_input[CONF_LOCALAI_PORT],
                    'https': user_input[CONF_LOCALAI_HTTPS]
                })
                await localai.validate()
                # add the mode to user_input
                return self.async_create_entry(title=f"LocalAI ({user_input[CONF_LOCALAI_IP_ADDRESS]})", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="localai",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="localai",
            data_schema=data_schema
        )

    async def async_step_ollama(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_OLLAMA_IP_ADDRESS): str,
            vol.Required(CONF_OLLAMA_PORT, default=11434): int,
            vol.Required(CONF_OLLAMA_HTTPS, default=False): bool,
        })

        if user_input is not None:
            # save provider to user_input
            user_input["provider"] = self.init_info["provider"]
            try:
                ollama = Ollama(self.hass, endpoint={
                    'ip_address': user_input[CONF_OLLAMA_IP_ADDRESS],
                    'port': user_input[CONF_OLLAMA_PORT],
                    'https': user_input[CONF_OLLAMA_HTTPS]
                })
                await ollama.validate()
                # add the mode to user_input
                return self.async_create_entry(title=f"Ollama ({user_input[CONF_OLLAMA_IP_ADDRESS]})", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="ollama",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="ollama",
            data_schema=data_schema,
        )

    async def async_step_openai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_OPENAI_API_KEY): str,
        })

        if user_input is not None:
            # save provider to user_input
            user_input["provider"] = self.init_info["provider"]
            try:
                openai = OpenAI(
                    self.hass, api_key=user_input[CONF_OPENAI_API_KEY])
                await openai.validate()
                # add the mode to user_input
                user_input["provider"] = self.init_info["provider"]
                return self.async_create_entry(title="OpenAI", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="openai",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="openai",
            data_schema=data_schema,
        )

    async def async_step_azure(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_AZURE_API_KEY): str,
            vol.Required(CONF_AZURE_BASE_URL, default="https://domain.openai.azure.com/"): str,
            vol.Required(CONF_AZURE_DEPLOYMENT, default="deployment"): str,
            vol.Required(CONF_AZURE_VERSION, default="2024-10-01-preview"): str,
        })

        if user_input is not None:
            # save provider to user_input
            user_input["provider"] = self.init_info["provider"]
            try:
                azure = AzureOpenAI(self.hass, api_key=user_input[CONF_AZURE_API_KEY], endpoint={
                    'base_url': ENDPOINT_AZURE,
                    'endpoint': user_input[CONF_AZURE_BASE_URL],
                    'deployment': user_input[CONF_AZURE_DEPLOYMENT],
                    'api_version': user_input[CONF_AZURE_VERSION]
                })
                await azure.validate()
                # add the mode to user_input
                user_input["provider"] = self.init_info["provider"]
                return self.async_create_entry(title="Azure", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="azure",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="azure",
            data_schema=data_schema,
        )

    async def async_step_anthropic(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_ANTHROPIC_API_KEY): str,
        })

        if user_input is not None:
            # save provider to user_input
            user_input["provider"] = self.init_info["provider"]
            try:
                anthropic = Anthropic(
                    self.hass, api_key=user_input[CONF_ANTHROPIC_API_KEY])
                await anthropic.validate()
                # add the mode to user_input
                user_input["provider"] = self.init_info["provider"]
                return self.async_create_entry(title="Anthropic Claude", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="anthropic",
                    data_schema=data_schema,
                    errors={"base": "empty_api_key"}
                )

        return self.async_show_form(
            step_id="anthropic",
            data_schema=data_schema,
        )

    async def async_step_google(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_GOOGLE_API_KEY): str,
        })

        if user_input is not None:
            # save provider to user_input
            user_input["provider"] = self.init_info["provider"]
            try:
                google = Google(
                    self.hass, api_key=user_input[CONF_GOOGLE_API_KEY])
                await google.validate()
                # add the mode to user_input
                user_input["provider"] = self.init_info["provider"]
                return self.async_create_entry(title="Google Gemini", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="google",
                    data_schema=data_schema,
                    errors={"base": "empty_api_key"}
                )

        return self.async_show_form(
            step_id="google",
            data_schema=data_schema,
        )

    async def async_step_groq(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_GROQ_API_KEY): str,
        })

        if user_input is not None:
            # save provider to user_input
            user_input["provider"] = self.init_info["provider"]
            try:
                groq = Groq(self.hass, api_key=user_input[CONF_GROQ_API_KEY])
                await groq.validate()
                # add the mode to user_input
                user_input["provider"] = self.init_info["provider"]
                return self.async_create_entry(title="Groq", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="groq",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="groq",
            data_schema=data_schema,
        )

    async def async_step_custom_openai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_CUSTOM_OPENAI_ENDPOINT): str,
            vol.Optional(CONF_CUSTOM_OPENAI_API_KEY): str,
        })

        if user_input is not None:
            # save provider to user_input
            user_input["provider"] = self.init_info["provider"]
            try:
                custom_openai = OpenAI(self.hass, api_key=user_input[CONF_CUSTOM_OPENAI_API_KEY], endpoint={
                    'base_url': user_input[CONF_CUSTOM_OPENAI_ENDPOINT]
                })
                await custom_openai.validate()
                # add the mode to user_input
                user_input["provider"] = self.init_info["provider"]
                return self.async_create_entry(title="Custom OpenAI compatible Provider", data=user_input)
            except ServiceValidationError as e:
                _LOGGER.error(f"Validation failed: {e}")
                return self.async_show_form(
                    step_id="custom_openai",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="custom_openai",
            data_schema=data_schema,
        )

    async def async_step_semantic_index(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_RETENTION_TIME, default=7): int,
        })
        if user_input is not None:
            user_input["provider"] = self.init_info["provider"]

            for uid in self.hass.data[DOMAIN]:
                if 'retention_time' in self.hass.data[DOMAIN][uid]:
                    self.async_abort(reason="already_configured")
                # add the mode to user_input
            return self.async_create_entry(title="LLM Vision Events", data=user_input)

        return self.async_show_form(
            step_id="semantic_index",
            data_schema=data_schema,
        )
