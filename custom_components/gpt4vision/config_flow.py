from homeassistant import config_entries
from homeassistant.helpers.selector import selector
from homeassistant.exceptions import ServiceValidationError
from .const import DOMAIN, CONF_API_KEY, CONF_MODE, CONF_IP_ADDRESS, CONF_PORT
import voluptuous as vol
import logging
import socket

_LOGGER = logging.getLogger(__name__)


async def validate_mode(user_input: dict):
    # check CONF_MODE is not empty
    _LOGGER.debug(f"Validating mode: {user_input[CONF_MODE]}")
    if not user_input[CONF_MODE]:
        raise ServiceValidationError("empty_mode")


def validate_localai(user_input: dict):
    # check CONF_IP_ADDRESS is not empty
    _LOGGER.debug(f"Validating IP Address: {user_input[CONF_IP_ADDRESS]}")
    if not user_input[CONF_IP_ADDRESS]:
        raise ServiceValidationError("empty_ip_address")

    # check CONF_PORT is not empty
    _LOGGER.debug(f"Validating Port: {user_input[CONF_PORT]}")
    if not user_input[CONF_PORT]:
        raise ServiceValidationError("empty_port")
    # perform handshake with LocalAI server
    if not handshake(user_input[CONF_IP_ADDRESS], user_input[CONF_PORT]):
        raise ServiceValidationError("handshake_failed")

def validate_openai(user_input: dict):
    # check CONF_API_KEY is not empty
    _LOGGER.debug(f"Validating API Key: {user_input[CONF_API_KEY]}")
    if not user_input[CONF_API_KEY]:
        raise ServiceValidationError("empty_api_key")


def handshake(ip_address, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)  # One second timeout
    try:
        sock.connect((ip_address, port))
        sock.close()
        return True
    except socket.error:
        return False

class gpt4visionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_user(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_MODE, default="OpenAI"): selector({
                "select": {
                    "options": ["OpenAI", "LocalAI"],
                    "mode": "dropdown",
                    "sort": True,
                    "custom_value": False
                }
            }),
        })

        if user_input is not None:
            self.init_info = user_input
            if user_input[CONF_MODE] == "LocalAI":
                _LOGGER.debug("LocalAI selected")
                return await self.async_step_localai()
            else:
                _LOGGER.debug("OpenAI selected")
                return await self.async_step_openai()

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders=user_input
        )

    async def async_step_localai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_IP_ADDRESS): str,
            vol.Required(CONF_PORT, default=8080): int,
        })

        if user_input is not None:
            try:
                validate_localai(user_input)
                # add the mode to user_input
                user_input[CONF_MODE] = self.init_info[CONF_MODE]
                _LOGGER.error(f"LocalAI: {user_input}")
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

    async def async_step_openai(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_API_KEY): str,
        })

        if user_input is not None:
            try:
                validate_openai(user_input)
                # add the mode to user_input
                user_input[CONF_MODE] = self.init_info[CONF_MODE]
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
