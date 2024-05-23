from homeassistant import config_entries
from homeassistant.helpers.selector import selector
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN, 
    CONF_PROVIDER,
    CONF_OPENAI_API_KEY, 
    CONF_LOCALAI_IP_ADDRESS, 
    CONF_LOCALAI_PORT,
    CONF_OLLAMA_IP_ADDRESS,
    CONF_OLLAMA_PORT
)
import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)


async def validate_mode(user_input: dict):
    # check CONF_MODE is not empty
    if not user_input[CONF_PROVIDER]:
        raise ServiceValidationError("empty_mode")


async def validate_localai(hass, user_input: dict):
    # check CONF_IP_ADDRESS is not empty
    if not user_input[CONF_LOCALAI_IP_ADDRESS]:
        raise ServiceValidationError("empty_ip_address")

    # check CONF_PORT is not empty
    if not user_input[CONF_LOCALAI_PORT]:
        raise ServiceValidationError("empty_port")
    # perform handshake with LocalAI server
    if not await validate_connection(hass, user_input[CONF_LOCALAI_IP_ADDRESS], user_input[CONF_LOCALAI_PORT], "/readyz"):
        raise ServiceValidationError("handshake_failed")


async def validate_ollama(hass, user_input: dict):
    # check CONF_IP_ADDRESS is not empty
    if not user_input[CONF_OLLAMA_IP_ADDRESS]:
        raise ServiceValidationError("empty_ip_address")

    # check CONF_PORT is not empty
    if not user_input[CONF_OLLAMA_PORT]:
        raise ServiceValidationError("empty_port")
    # perform handshake with LocalAI server
    if not await validate_connection(hass, user_input[CONF_OLLAMA_IP_ADDRESS], user_input[CONF_OLLAMA_PORT], "/api/tags"):
        raise ServiceValidationError("handshake_failed")


def validate_openai(user_input: dict):
    # check CONF_API_KEY is not empty
    if not user_input[CONF_OPENAI_API_KEY]:
        raise ServiceValidationError("empty_api_key")


async def validate_connection(hass, ip_address, port, endpoint, expected_status=200):
    session = async_get_clientsession(hass)
    url = f'http://{ip_address}:{port}{endpoint}'
    try:
        response = await session.get(url)
        if response.status == expected_status:
            return True
        else:
            return False
    except Exception as e:
        return False


class gpt4visionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_user(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required("provider", default="OpenAI"): selector({
                "select": {
                    "options": ["OpenAI", "LocalAI", "Ollama"],
                    "mode": "dropdown",
                    "sort": True,
                    "custom_value": False
                }
            }),
        })

        if user_input is not None:
            self.init_info = user_input
            if user_input[CONF_PROVIDER] == "LocalAI":
                if DOMAIN in self.hass.data and CONF_LOCALAI_IP_ADDRESS in self.hass.data[DOMAIN] and CONF_LOCALAI_PORT in self.hass.data[DOMAIN]:
                    return self.async_abort(reason="already_configured")
                return await self.async_step_localai()
            elif user_input[CONF_PROVIDER] == "Ollama":
                if DOMAIN in self.hass.data and CONF_OLLAMA_IP_ADDRESS in self.hass.data[DOMAIN] and CONF_OLLAMA_PORT in self.hass.data[DOMAIN]:
                    return self.async_abort(reason="already_configured")
                return await self.async_step_ollama()
            else:
                if DOMAIN in self.hass.data and CONF_OPENAI_API_KEY in self.hass.data[DOMAIN]:
                    return self.async_abort(reason="already_configured")
                return await self.async_step_openai()

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders=user_input
        )

    async def async_step_localai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_LOCALAI_IP_ADDRESS): str,
            vol.Required(CONF_LOCALAI_PORT, default=8080): int,
        })

        if user_input is not None:
            try:
                validate_localai(self.hass, user_input)
                # add the mode to user_input
                return self.async_create_entry(title="GPT4Vision LocalAI", data=user_input)
            except ServiceValidationError as e:
                return self.async_show_form(
                    step_id="localai",
                    data_schema=data_schema,
                    errors={"base": "handshake_failed"}
                )

        return self.async_show_form(
            step_id="localai",
            data_schema=data_schema,
        )

    async def async_step_ollama(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_OLLAMA_IP_ADDRESS): str,
            vol.Required(CONF_OLLAMA_PORT, default=11434): int,
        })

        if user_input is not None:
            try:
                validate_ollama(self.hass, user_input)
                # add the mode to user_input
                return self.async_create_entry(title="GPT4Vision Ollama", data=user_input)
            except ServiceValidationError as e:
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
            try:
                validate_openai(user_input)
                # add the mode to user_input
                user_input["provider"] = self.init_info["provider"]
                return self.async_create_entry(title="GPT4Vision OpenAI", data=user_input)
            except ServiceValidationError as e:
                return self.async_show_form(
                    step_id="openai",
                    data_schema=data_schema,
                    errors={"base": "empty_api_key"}
                )

        return self.async_show_form(
            step_id="openai",
            data_schema=data_schema,
        )
