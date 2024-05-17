from homeassistant import config_entries
from .const import DOMAIN, CONF_API_KEY
import voluptuous as vol


class gpt4visionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        data_schema = vol.Schema({
            vol.Required(CONF_API_KEY): str
        })

        if user_input is not None:
            # Save the API key
            return self.async_create_entry(title="GPT4Vision Configuration", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders=user_input
        )
