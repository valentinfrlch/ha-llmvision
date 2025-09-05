from .const import (
    DOMAIN,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TITLE_PROMPT,
    CONF_MEMORY_PROVIDER,
)
from abc import ABC, abstractmethod
import base64
import io
from PIL import Image
import logging
import requests
import sqlite3
import json
import numpy as np

_LOGGER = logging.getLogger(__name__)


def get_provider(provider_name, **kwargs):
    """
    Factory to return the correct VectorProvider subclass.
    Example kwargs: url, model, api_key, etc.
    """
    provider_name = provider_name.lower()
    if provider_name == "ollama":
        return Ollama(kwargs.get("url"), kwargs.get("model"))
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


class VectorProvider(ABC):
    async def add_texts(self, texts: list, namespace: str) -> None:
        """Add texts to the vector database"""
        pass

    async def query(self, query: str, namespace: str, top_k: int) -> list:
        """Query the vector database"""
        pass

    @abstractmethod
    async def get_embeddings(self, text: str) -> list:
        """Get embeddings from Ollama"""


class Ollama(VectorProvider):
    def __init__(self, url, model):
        self.url = url
        self.model = model

    @property
    def models(self):
        response = requests.get(f"{self.url}/api/tags")
        response.raise_for_status()
        return response.json()

    @property
    def loaded_models(self):
        response = requests.get(f"{self.url}/api/ps")
        response.raise_for_status()
        return response.json()

    def _check_health(self):
        response = requests.get(f"{self.url}")
        if response.text != "Ollama is running":
            raise ConnectionError("Ollama server is not running")

    def get_embeddings(self, text):
        response = requests.post(
            f"{self.url}/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        response.raise_for_status()
        return response.json()["embedding"]

class MemoryDB:
    def __init__(self, db_path="memory.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image TEXT,
                caption TEXT,
                embeddings TEXT,
                type TEXT
            )
        """)
        self.conn.commit()

    def add_item(self, image_b64, caption, embeddings, item_type):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO memory (image, caption, embeddings, type)
            VALUES (?, ?, ?, ?)
        """, (image_b64, caption, json.dumps(embeddings), item_type))
        self.conn.commit()

    def query_items(self, prompt_embedding, top_k=5):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, image, caption, embeddings, type FROM memory")
        items = cursor.fetchall()
        # Calculate cosine similarity
        scored = []
        for item in items:
            emb = np.array(json.loads(item[3]))
            score = self._cosine_similarity(np.array(prompt_embedding), emb)
            scored.append((score, item))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [item for score, item in scored[:top_k]]

    def _cosine_similarity(self, a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def close(self):
        self.conn.close()


class Memory:
    def __init__(self, hass, provider, strings=[], paths=[], system_prompt=None):
        self.hass = hass
        self.provider = provider
        self.db = MemoryDB(hass.config.path(f"{DOMAIN}/memory.db"))
        self._system_prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
        self._title_prompt = DEFAULT_TITLE_PROMPT
        self.memory_strings = strings
        self.memory_paths = paths
        self.memory_images = []

        _LOGGER.debug(self)

    async def add_memory_item(self, image_b64, caption, item_type):
        embedding = await self.provider.get_embeddings(caption)
        self.db.add_item(image_b64, caption, embedding, item_type)

    async def inject_relevant_memories(self, prompt, top_k=5, memory_type="OpenAI"):
        # Get embedding for the prompt
        prompt_embedding = await self.provider.get_embeddings(prompt)
        # Query DB for relevant items
        items = self.db.query_items(prompt_embedding, top_k=top_k)
        # Format for LLM context
        content = []
        memory_prompt = "The following images along with descriptions serve as reference. They are not to be mentioned in the response."
        if items:
            if memory_type in ["OpenAI", "OpenAI-legacy", "Anthropic"]:
                content.append({"type": "text", "text": memory_prompt})
            elif memory_type in ["Ollama"]:
                content.append({"role": "user", "content": memory_prompt})
            elif memory_type in ["Google", "AWS"]:
                content.append({"text": memory_prompt})

        for item in items:
            _, image, caption, _, item_type = item
            if memory_type in ["OpenAI", "OpenAI-legacy"]:
                content.append({"type": "text", "text": caption + ":"})
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}})
            elif memory_type == "Ollama":
                content.append({"role": "user", "content": caption + ":", "images": [image]})
            elif memory_type == "Anthropic":
                content.append({"type": "text", "text": caption + ":"})
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image}})
            elif memory_type == "Google":
                content.append({"text": caption + ":"})
                content.append({"inline_data": {"mime_type": "image/jpeg", "data": image}})
            elif memory_type == "AWS":
                content.append({"text": caption + ":"})
                content.append({"image": {"format": "jpeg", "source": {"bytes": base64.b64decode(image)}}})
        return content

    @property
    def system_prompt(self) -> str:
        return "System prompt: " + self._system_prompt

    @property
    def title_prompt(self) -> str:
        return self._title_prompt

    def close(self):
        self.db.close()

    def __str__(self):
        return f"Memory({self.memory_strings}, {self.memory_paths}, {len(self.memory_images)})"

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
