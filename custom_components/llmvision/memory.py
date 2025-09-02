from .const import (
    DOMAIN,
    CONF_MEMORY_PATHS,
    CONF_MEMORY_IMAGES_ENCODED,
    CONF_MEMORY_STRINGS,
    CONF_SYSTEM_PROMPT,
    CONF_TITLE_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TITLE_PROMPT,
)
import base64
import io
from PIL import Image
import logging

_LOGGER = logging.getLogger(__name__)


class Memory:
    def __init__(self, hass, strings=[], paths=[], system_prompt=None):
        self.hass = hass
        self.entry = self._find_memory_entry()
        if self.entry is None:

            self._system_prompt = (
                system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
            )
            self._title_prompt = DEFAULT_TITLE_PROMPT
            self.memory_strings = strings
            self.memory_paths = paths
            self.memory_images = []

        else:
            self._system_prompt = (
                system_prompt
                if system_prompt
                else self.entry.data.get(CONF_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT)
            )
            self._title_prompt = self.entry.data.get(
                CONF_TITLE_PROMPT, DEFAULT_TITLE_PROMPT
            )
            self.memory_strings = self.entry.data.get(CONF_MEMORY_STRINGS, strings)
            self.memory_paths = self.entry.data.get(CONF_MEMORY_PATHS, paths)
            self.memory_images = self.entry.data.get(CONF_MEMORY_IMAGES_ENCODED, [])

        _LOGGER.debug(self)

    def _get_memory_images(self, memory_type="OpenAI") -> list:
        content = []
        memory_prompt = "The following images along with descriptions serve as reference. They are not to be mentioned in the response."

        if memory_type == "OpenAI":
            if self.memory_images:
                content.append({"type": "text", "text": memory_prompt})
            for image in self.memory_images:
                tag = self.memory_strings[self.memory_images.index(image)]

                content.append({"type": "text", "text": tag + ":"})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                    }
                )

        elif memory_type == "OpenAI-legacy":
            if self.memory_images:
                content.append({"type": "text", "text": memory_prompt})
            for image in self.memory_images:
                tag = self.memory_strings[self.memory_images.index(image)]

                content.append({"type": "text", "text": tag + ":"})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                    }
                )

        elif memory_type == "Ollama":
            if self.memory_images:
                content.append({"role": "user", "content": memory_prompt})
            for image in self.memory_images:
                tag = self.memory_strings[self.memory_images.index(image)]

                content.append(
                    {"role": "user", "content": tag + ":", "images": [image]}
                )

        elif memory_type == "Anthropic":
            if self.memory_images:
                content.append({"type": "text", "text": memory_prompt})
            for image in self.memory_images:
                tag = self.memory_strings[self.memory_images.index(image)]

                content.append({"type": "text", "text": tag + ":"})
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": f"{image}",
                        },
                    }
                )
        elif memory_type == "Google":
            if self.memory_images:
                content.append({"text": memory_prompt})
            for image in self.memory_images:
                tag = self.memory_strings[self.memory_images.index(image)]

                content.append({"text": tag + ":"})
                content.append(
                    {"inline_data": {"mime_type": "image/jpeg", "data": image}}
                )
        elif memory_type == "AWS":
            if self.memory_images:
                content.append({"text": memory_prompt})
            for image in self.memory_images:
                tag = self.memory_strings[self.memory_images.index(image)]

                content.append({"text": tag + ":"})
                content.append(
                    {
                        "image": {
                            "format": "jpeg",
                            "source": {"bytes": base64.b64decode(image)},
                        }
                    }
                )
        else:
            return None

        return content

    @property
    def system_prompt(self) -> str:
        return "System prompt: " + self._system_prompt

    @property
    def title_prompt(self) -> str:
        return self._title_prompt

    def _find_memory_entry(self):
        memory_entry = None
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            # Check if the config entry is empty
            if entry.data["provider"] == "Settings":
                memory_entry = entry
                break

        return memory_entry

    async def _encode_images(self, image_paths):
        """Encode images as base64"""
        encoded_images = []

        for image_path in image_paths:
            img = await self.hass.loop.run_in_executor(None, Image.open, image_path)
            with img:
                await self.hass.loop.run_in_executor(None, img.load)
                # calculate new height and width based on aspect ratio
                width, height = img.size
                aspect_ratio = width / height
                if aspect_ratio > 1:
                    new_width = 512
                    new_height = int(512 / aspect_ratio)
                else:
                    new_height = 512
                    new_width = int(512 * aspect_ratio)
                img = img.resize((new_width, new_height))

                # Convert Memory Images to RGB mode if needed
                if img.mode == "RGBA":
                    img = img.convert("RGB")

                # Encode the image to base64
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="JPEG")
                base64_image = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
                encoded_images.append(base64_image)

        return encoded_images

    async def _update_memory(self):
        """Manage encoded images"""
        # check if len(memory_paths) != len(memory_images)
        if len(self.memory_paths) != len(self.memory_images):
            self.memory_images = await self._encode_images(self.memory_paths)

            # update memory with new images
            memory = self.entry.data.copy()
            memory["images"] = self.memory_images
            self.hass.config_entries.async_update_entry(self.entry, data=memory)

    def __str__(self):
        return f"Memory({self.memory_strings}, {self.memory_paths}, {len(self.memory_images)})"
