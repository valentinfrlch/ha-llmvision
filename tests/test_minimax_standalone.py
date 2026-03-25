"""Standalone tests for MiniMax provider integration.

These tests mock homeassistant dependencies and directly load only the modules
needed for testing, bypassing __init__.py which uses Python 3.12+ syntax.
"""
import sys
import os
import json
import types
import asyncio
import importlib
import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock


# --- Mock homeassistant modules before importing component code ---

def _setup_ha_mocks():
    """Create mock homeassistant modules for testing."""
    ha_exceptions = types.ModuleType("homeassistant.exceptions")

    class ServiceValidationError(Exception):
        pass

    ha_exceptions.ServiceValidationError = ServiceValidationError

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []

    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers.__path__ = []
    ha_helpers_aiohttp = types.ModuleType("homeassistant.helpers.aiohttp_client")
    ha_helpers_aiohttp.async_get_clientsession = Mock(return_value=Mock())

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = type("HomeAssistant", (), {})

    ha_config_entries = types.ModuleType("homeassistant.config_entries")
    ha_config_entries.ConfigEntry = type("ConfigEntry", (), {})

    mods = {
        "homeassistant": ha,
        "homeassistant.exceptions": ha_exceptions,
        "homeassistant.helpers": ha_helpers,
        "homeassistant.helpers.aiohttp_client": ha_helpers_aiohttp,
        "homeassistant.core": ha_core,
        "homeassistant.config_entries": ha_config_entries,
    }
    sys.modules.update(mods)

    if "boto3" not in sys.modules:
        sys.modules["boto3"] = MagicMock()

    return ServiceValidationError


ServiceValidationError = _setup_ha_mocks()

# Prevent __init__.py from running; create a stub package
_pkg_name = "custom_components.llmvision"
_pkg = types.ModuleType(_pkg_name)
_pkg.__path__ = [os.path.join(os.path.dirname(__file__), "..", "custom_components", "llmvision")]
_pkg.__package__ = _pkg_name
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules["custom_components"].__path__ = [os.path.join(os.path.dirname(__file__), "..", "custom_components")]
sys.modules[_pkg_name] = _pkg

# Now load const and providers directly
import importlib.util

_base_dir = os.path.join(os.path.dirname(__file__), "..", "custom_components", "llmvision")

def _load_module(name, filepath):
    spec = importlib.util.spec_from_file_location(
        f"custom_components.llmvision.{name}",
        os.path.join(_base_dir, filepath),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"custom_components.llmvision.{name}"] = mod
    spec.loader.exec_module(mod)
    return mod

const_mod = _load_module("const", "const.py")
providers_mod = _load_module("providers", "providers.py")

# Pull out what we need
DOMAIN = const_mod.DOMAIN
DEFAULT_MINIMAX_MODEL = const_mod.DEFAULT_MINIMAX_MODEL
ENDPOINT_MINIMAX = const_mod.ENDPOINT_MINIMAX
DEFAULT_OPENAI_MODEL = const_mod.DEFAULT_OPENAI_MODEL
OpenAI = providers_mod.OpenAI
Request = providers_mod.Request
ProviderFactory = providers_mod.ProviderFactory


def _make_mock_hass():
    hass = Mock()
    hass.data = {}
    hass.config_entries = Mock()
    hass.config_entries.async_entries = Mock(return_value=[])
    hass.loop = Mock()
    hass.loop.run_in_executor = AsyncMock()
    hass.config = Mock()
    hass.config.path = Mock(return_value="/mock/path")
    return hass


class TestMiniMaxConstants(unittest.TestCase):
    """Test MiniMax constants."""

    def test_default_model(self):
        self.assertEqual(DEFAULT_MINIMAX_MODEL, "MiniMax-M1")

    def test_endpoint(self):
        self.assertEqual(ENDPOINT_MINIMAX, "https://api.minimax.io/v1/chat/completions")

    def test_endpoint_is_openai_compatible(self):
        self.assertTrue(ENDPOINT_MINIMAX.endswith("/v1/chat/completions"))


class TestMiniMaxProviderFactory(unittest.TestCase):
    """Test ProviderFactory creates MiniMax provider correctly."""

    def test_create_minimax(self):
        hass = _make_mock_hass()
        provider = ProviderFactory.create(hass, "MiniMax", {"api_key": "test_key"}, "MiniMax-M1")

        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, OpenAI)
        self.assertEqual(provider.model, "MiniMax-M1")
        self.assertEqual(provider.api_key, "test_key")

    def test_create_minimax_endpoint(self):
        hass = _make_mock_hass()
        provider = ProviderFactory.create(hass, "MiniMax", {"api_key": "test_key"}, "MiniMax-M1")

        self.assertEqual(provider.endpoint.get("base_url"), ENDPOINT_MINIMAX)

    def test_create_minimax_empty_key(self):
        hass = _make_mock_hass()
        provider = ProviderFactory.create(hass, "MiniMax", {}, "MiniMax-M1")

        self.assertEqual(provider.api_key, "")

    def test_create_invalid_provider(self):
        hass = _make_mock_hass()

        with self.assertRaises(ServiceValidationError):
            ProviderFactory.create(hass, "InvalidProvider", {"api_key": "test"}, "model")


class TestMiniMaxDefaultModel(unittest.TestCase):
    """Test MiniMax default model mapping."""

    def test_default_model_mapping(self):
        hass = _make_mock_hass()
        hass.data = {DOMAIN: {"entry": {"provider": "MiniMax"}}}

        request = Request(hass, "test", 1000, 0.5)
        self.assertEqual(request.get_default_model("entry"), DEFAULT_MINIMAX_MODEL)

    def test_default_model_from_config(self):
        hass = _make_mock_hass()
        hass.data = {DOMAIN: {"entry": {"provider": "MiniMax", "default_model": "MiniMax-M1"}}}

        request = Request(hass, "test", 1000, 0.5)
        self.assertEqual(request.get_default_model("entry"), "MiniMax-M1")

    def test_openai_default_model_still_works(self):
        hass = _make_mock_hass()
        hass.data = {DOMAIN: {"entry": {"provider": "OpenAI"}}}

        request = Request(hass, "test", 1000, 0.5)
        self.assertEqual(request.get_default_model("entry"), DEFAULT_OPENAI_MODEL)


class TestMiniMaxProviderBehavior(unittest.TestCase):
    """Test MiniMax provider behavior (inherits from OpenAI)."""

    def _create_provider(self, api_key="test_key", model="MiniMax-M1"):
        hass = _make_mock_hass()
        return ProviderFactory.create(hass, "MiniMax", {"api_key": api_key}, model), hass

    def test_supports_structured_output(self):
        provider, _ = self._create_provider()
        self.assertTrue(provider.supports_structured_output())

    def test_generate_headers(self):
        provider, _ = self._create_provider(api_key="minimax_api_key_123")
        headers = provider._generate_headers()

        self.assertEqual(headers["Content-type"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer minimax_api_key_123")

    def test_prepare_vision_data(self):
        provider, hass = self._create_provider()

        call = Mock()
        call.max_tokens = 1000
        call.base64_images = ["base64_image_data"]
        call.filenames = ["test.jpg"]
        call.message = "Describe this image"
        call.provider = "test_provider"
        call.response_format = "text"
        call.use_memory = False

        hass.data = {DOMAIN: {"test_provider": {"provider": "MiniMax", "temperature": 0.5, "top_p": 0.9}}}

        with patch.object(provider, '_get_system_prompt', return_value="System prompt"):
            result = provider._prepare_vision_data(call)

        self.assertEqual(result["model"], "MiniMax-M1")
        self.assertEqual(result["max_completion_tokens"], 1000)
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(result["messages"][0]["role"], "system")
        self.assertEqual(result["messages"][1]["role"], "user")

        # Check image is included
        user_content = result["messages"][1]["content"]
        has_image = any(isinstance(item, dict) and item.get("type") == "image_url" for item in user_content)
        self.assertTrue(has_image)

    def test_prepare_text_data(self):
        provider, hass = self._create_provider()

        call = Mock()
        call.max_tokens = 1000
        call.message = "Generate a title"
        call.provider = "test_provider"

        hass.data = {DOMAIN: {"test_provider": {"provider": "MiniMax", "temperature": 0.5, "top_p": 0.9}}}

        with patch.object(provider, '_get_title_prompt', return_value="Title prompt"):
            result = provider._prepare_text_data(call)

        self.assertEqual(result["model"], "MiniMax-M1")
        self.assertEqual(result["max_completion_tokens"], 1000)
        self.assertEqual(len(result["messages"]), 2)

    def test_prepare_vision_data_with_structured_output(self):
        provider, hass = self._create_provider()

        call = Mock()
        call.max_tokens = 1000
        call.base64_images = ["base64_image_data"]
        call.filenames = ["test.jpg"]
        call.message = "Extract data"
        call.provider = "test_provider"
        call.response_format = "json"
        call.structure = '{"type": "object", "properties": {"count": {"type": "integer"}}}'
        call.use_memory = False

        hass.data = {DOMAIN: {"test_provider": {"provider": "MiniMax", "temperature": 0.5, "top_p": 0.9}}}

        with patch.object(provider, '_get_system_prompt', return_value="System prompt"):
            result = provider._prepare_vision_data(call)

        self.assertIn("response_format", result)
        self.assertEqual(result["response_format"]["type"], "json_schema")
        self.assertTrue(result["response_format"]["json_schema"]["strict"])

    def test_prepare_vision_data_multiple_images(self):
        provider, hass = self._create_provider()

        call = Mock()
        call.max_tokens = 1000
        call.base64_images = ["img1", "img2", "img3"]
        call.filenames = ["cam1.jpg", "cam2.jpg", "cam3.jpg"]
        call.message = "What do you see?"
        call.provider = "test_provider"
        call.response_format = "text"
        call.use_memory = False

        hass.data = {DOMAIN: {"test_provider": {"provider": "MiniMax", "temperature": 0.5, "top_p": 0.9}}}

        with patch.object(provider, '_get_system_prompt', return_value="System prompt"):
            result = provider._prepare_vision_data(call)

        user_content = result["messages"][1]["content"]
        image_items = [item for item in user_content if isinstance(item, dict) and item.get("type") == "image_url"]
        self.assertEqual(len(image_items), 3)

    def test_temperature_and_top_p_passed(self):
        provider, hass = self._create_provider()

        call = Mock()
        call.max_tokens = 500
        call.base64_images = ["img"]
        call.filenames = ["test.jpg"]
        call.message = "test"
        call.provider = "test_provider"
        call.response_format = "text"
        call.use_memory = False

        hass.data = {DOMAIN: {"test_provider": {"provider": "MiniMax", "temperature": 0.3, "top_p": 0.7}}}

        with patch.object(provider, '_get_system_prompt', return_value="System prompt"):
            result = provider._prepare_vision_data(call)

        self.assertEqual(result["temperature"], 0.3)
        self.assertEqual(result["top_p"], 0.7)


class TestMiniMaxAsyncOperations(unittest.TestCase):
    """Test MiniMax async operations."""

    def _create_provider(self, api_key="test_key", model="MiniMax-M1"):
        hass = _make_mock_hass()
        return ProviderFactory.create(hass, "MiniMax", {"api_key": api_key}, model), hass

    def test_make_request(self):
        provider, _ = self._create_provider()

        mock_response = {"choices": [{"message": {"content": "A person walking a dog."}}]}

        async def run():
            with patch.object(provider, '_post', new_callable=AsyncMock, return_value=mock_response):
                return await provider._make_request({"model": "MiniMax-M1", "messages": []})

        result = asyncio.get_event_loop().run_until_complete(run())
        self.assertEqual(result, "A person walking a dog.")

    def test_make_request_empty_response(self):
        provider, _ = self._create_provider()

        mock_response = {"choices": []}

        async def run():
            with patch.object(provider, '_post', new_callable=AsyncMock, return_value=mock_response):
                with self.assertRaises(ServiceValidationError):
                    await provider._make_request({"model": "MiniMax-M1", "messages": []})

        asyncio.get_event_loop().run_until_complete(run())

    def test_validate_success(self):
        provider, _ = self._create_provider(api_key="valid_key")

        mock_response = {"choices": [{"message": {"content": "Hi"}}]}

        async def run():
            with patch.object(provider, '_post', new_callable=AsyncMock, return_value=mock_response):
                await provider.validate()

        asyncio.get_event_loop().run_until_complete(run())

    def test_validate_empty_key(self):
        provider, _ = self._create_provider(api_key="")

        async def run():
            with self.assertRaises(ServiceValidationError):
                await provider.validate()

        asyncio.get_event_loop().run_until_complete(run())

    def test_vision_request_flow(self):
        provider, hass = self._create_provider()

        call = Mock()
        call.max_tokens = 1000
        call.base64_images = ["base64img"]
        call.filenames = ["test.jpg"]
        call.message = "Analyze"
        call.provider = "test_provider"
        call.response_format = "text"
        call.use_memory = False

        hass.data = {DOMAIN: {"test_provider": {"provider": "MiniMax", "temperature": 0.5, "top_p": 0.9}}}

        mock_response = {"choices": [{"message": {"content": "Analysis result"}}]}

        async def run():
            with patch.object(provider, '_post', new_callable=AsyncMock, return_value=mock_response):
                with patch.object(provider, '_get_system_prompt', return_value="System prompt"):
                    return await provider.vision_request(call)

        result = asyncio.get_event_loop().run_until_complete(run())
        self.assertEqual(result, "Analysis result")


class TestMiniMaxTranslations(unittest.TestCase):
    """Test MiniMax translation entries."""

    def _get_translations_dir(self):
        return os.path.join(os.path.dirname(__file__), "..", "custom_components", "llmvision", "translations")

    def test_english_translation_exists(self):
        with open(os.path.join(self._get_translations_dir(), "en.json")) as f:
            data = json.load(f)

        steps = data["config"]["step"]
        self.assertIn("minimax", steps)
        self.assertEqual(steps["minimax"]["title"], "Configure MiniMax")
        self.assertIn("connection_section", steps["minimax"]["sections"])
        self.assertIn("model_section", steps["minimax"]["sections"])

    def test_all_translations_have_minimax(self):
        for fname in os.listdir(self._get_translations_dir()):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self._get_translations_dir(), fname)
            with open(fpath) as f:
                data = json.load(f)

            steps = data.get("config", {}).get("step", {})
            self.assertIn("minimax", steps, f"Missing minimax step in {fname}")
            self.assertIn("title", steps["minimax"], f"Missing title in {fname}")
            self.assertIn("connection_section", steps["minimax"].get("sections", {}), f"Missing connection_section in {fname}")
            self.assertIn("model_section", steps["minimax"].get("sections", {}), f"Missing model_section in {fname}")

    def test_all_translation_files_valid_json(self):
        for fname in os.listdir(self._get_translations_dir()):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self._get_translations_dir(), fname)
            with open(fpath) as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    self.fail(f"Invalid JSON in {fname}: {e}")


class TestMiniMaxCodeIntegration(unittest.TestCase):
    """Integration tests for MiniMax presence in source files."""

    def _read_file(self, relpath):
        path = os.path.join(os.path.dirname(__file__), "..", relpath)
        with open(path) as f:
            return f.read()

    def test_minimax_in_const(self):
        content = self._read_file("custom_components/llmvision/const.py")
        self.assertIn("DEFAULT_MINIMAX_MODEL", content)
        self.assertIn("ENDPOINT_MINIMAX", content)

    def test_minimax_in_providers(self):
        content = self._read_file("custom_components/llmvision/providers.py")
        self.assertIn("MiniMax", content)
        self.assertIn("ENDPOINT_MINIMAX", content)
        self.assertIn("DEFAULT_MINIMAX_MODEL", content)

    def test_minimax_in_config_flow(self):
        content = self._read_file("custom_components/llmvision/config_flow.py")
        self.assertIn('"MiniMax"', content)
        self.assertIn("async_step_minimax", content)
        self.assertIn("ENDPOINT_MINIMAX", content)
        self.assertIn("DEFAULT_MINIMAX_MODEL", content)

    def test_minimax_in_readme(self):
        content = self._read_file("README.md")
        self.assertIn("MiniMax", content)

    def test_minimax_in_provider_dropdown(self):
        """Verify MiniMax is in the provider selection dropdown list."""
        content = self._read_file("custom_components/llmvision/config_flow.py")
        # Find the options list in async_step_user
        self.assertIn('"MiniMax",', content)

    def test_minimax_in_handle_provider_map(self):
        """Verify MiniMax is in the handle_provider routing dict."""
        content = self._read_file("custom_components/llmvision/config_flow.py")
        self.assertIn('"MiniMax": self.async_step_minimax', content)


if __name__ == "__main__":
    unittest.main()
