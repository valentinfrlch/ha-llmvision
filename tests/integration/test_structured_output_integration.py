#!/usr/bin/env python3
"""
Integration test for structured output implementation in providers.py
Tests the actual provider code with real API calls to validate Phase 1 implementation.
"""

import os
import sys
import json
import base64
import asyncio
import pytest
from unittest.mock import Mock
from PIL import Image
import io
import aiohttp

# Add project root to path to import custom_components
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import the actual integration code
from custom_components.llmvision.providers import Request
from custom_components.llmvision.const import (
    DOMAIN, CONF_PROVIDER, CONF_API_KEY, CONF_DEFAULT_MODEL,
    RESPONSE_FORMAT, STRUCTURE, CONF_IP_ADDRESS, CONF_PORT, CONF_HTTPS
)


def create_test_image_base64():
    """Create a simple test image and convert to base64"""
    img = Image.new('RGB', (50, 50), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


class MockConfigEntries:
    """Mock config entries"""
    
    def async_entries(self, domain):
        """Return empty list of entries"""
        return []


class MockHass:
    """Minimal mock Home Assistant that provides real aiohttp session"""
    
    def __init__(self):
        self.data = {DOMAIN: {}}
        self.config_entries = MockConfigEntries()
        self._session = aiohttp.ClientSession()
        
    def get_real_session(self, hass=None):
        """Get a real aiohttp session for actual API calls"""
        return self._session
        
    async def close_session(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def async_add_executor_job(self, func, *args, **kwargs):
        """Mock executor job for AWS Bedrock - just run the function directly"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)


class MockServiceCall:
    """Mock service call that matches the ServiceCallData interface"""
    
    def __init__(self, response_format="text", structure=None, base64_images=None, filenames=None, message="Test message"):
        self.response_format = response_format
        self.structure = structure
        self.base64_images = base64_images or []
        self.filenames = filenames or []
        self.message = message
        self.use_memory = False
        self.memory = None
        self.max_tokens = 100
        self.generate_title = False
        self.model = None


def setup_provider_config(hass, provider_name, api_key, model):
    """Set up provider configuration in mock hass"""
    provider_uid = f"test_{provider_name.lower()}_config"
    hass.data[DOMAIN][provider_uid] = {
        CONF_PROVIDER: provider_name,
        CONF_API_KEY: api_key,
        CONF_DEFAULT_MODEL: model
    }
    return provider_uid


@pytest.mark.integration
@pytest.mark.asyncio
class TestStructuredOutputIntegration:
    """Test structured output implementation in providers.py"""
    
    @pytest.mark.asyncio
    async def test_openai_structured_output(self):
        """Test OpenAI structured output through provider implementation"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")
            
        print("🧪 Testing OpenAI structured output via provider implementation...")
        
        # Set up mock hass with provider config
        hass = MockHass()
        provider_uid = setup_provider_config(hass, "OpenAI", api_key, "gpt-4o-mini")
        
        # Monkey patch to use real session
        import custom_components.llmvision.providers as providers_module
        original_get_session = providers_module.async_get_clientsession
        providers_module.async_get_clientsession = hass.get_real_session
        
        try:
            # Create Request instance
            request = Request(hass, "What is the dominant color in this image?", 100, 0.1)
            # Set images on the request object
            request.base64_images = [create_test_image_base64()]
            request.filenames = ["test_image.png"]
            
            # Define test schema
            color_schema = {
                "type": "object",
                "properties": {
                    "dominant_color": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_single_color": {"type": "boolean"}
                },
                "required": ["dominant_color", "confidence", "is_single_color"],
                "additionalProperties": False
            }
            
            # Create service call with structured output
            call = MockServiceCall(
                response_format="json",
                structure=json.dumps(color_schema),
                base64_images=[create_test_image_base64()],
                filenames=["test_image.png"],
                message="What is the dominant color in this image? Respond with confidence level and whether it's a single solid color."
            )
            # Add provider to call
            call.provider = provider_uid
            
            # Make actual API call through Request.call()
            response = await request.call(call)
            
            print(f"✅ Provider response: {response}")
            
            # Validate response structure
            assert "response_text" in response, "Response should contain response_text"
            
            # Parse and validate structured output
            structured_data = json.loads(response["response_text"])
            
            # Validate schema compliance
            assert "dominant_color" in structured_data, "Response should contain dominant_color"
            assert "confidence" in structured_data, "Response should contain confidence"
            assert "is_single_color" in structured_data, "Response should contain is_single_color"
            
            assert isinstance(structured_data["dominant_color"], str), "dominant_color should be string"
            assert isinstance(structured_data["confidence"], (int, float)), "confidence should be number"
            assert isinstance(structured_data["is_single_color"], bool), "is_single_color should be boolean"
            
            assert 0 <= structured_data["confidence"] <= 100, "confidence should be 0-100"
            assert "red" in structured_data["dominant_color"].lower() or "#ff0000" in structured_data["dominant_color"].lower(), "Should detect red color"
            
            print("✅ OpenAI structured output integration test passed!")
            
        finally:
            # Cleanup
            providers_module.async_get_clientsession = original_get_session
            await hass.close_session()

    @pytest.mark.asyncio
    async def test_anthropic_structured_output(self):
        """Test Anthropic structured output through provider implementation"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")
            
        print("🧪 Testing Anthropic structured output via provider implementation...")
        
        # Set up mock hass with provider config
        hass = MockHass()
        provider_uid = setup_provider_config(hass, "Anthropic", api_key, "claude-3-haiku-20240307")
        
        # Monkey patch to use real session
        import custom_components.llmvision.providers as providers_module
        original_get_session = providers_module.async_get_clientsession
        providers_module.async_get_clientsession = hass.get_real_session
        
        try:
            # Create Request instance
            request = Request(hass, "What is the dominant color in this image?", 100, 0.1)
            # Set images on the request object
            request.base64_images = [create_test_image_base64()]
            request.filenames = ["test_image.png"]
            
            # Define test schema
            color_schema = {
                "type": "object",
                "properties": {
                    "dominant_color": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_single_color": {"type": "boolean"}
                },
                "required": ["dominant_color", "confidence", "is_single_color"]
            }
            
            # Create service call with structured output
            call = MockServiceCall(
                response_format="json",
                structure=json.dumps(color_schema),
                base64_images=[create_test_image_base64()],
                filenames=["test_image.png"],
                message="What is the dominant color in this image? Respond with confidence level and whether it's a single solid color."
            )
            # Add provider to call
            call.provider = provider_uid
            
            # Make actual API call through Request.call()
            response = await request.call(call)
            
            print(f"✅ Provider response: {response}")
            
            # Validate response structure
            assert "response_text" in response, "Response should contain response_text"
            
            # Parse and validate structured output
            structured_data = json.loads(response["response_text"])
            
            # Validate schema compliance
            assert "dominant_color" in structured_data, "Response should contain dominant_color"
            assert "confidence" in structured_data, "Response should contain confidence"
            assert "is_single_color" in structured_data, "Response should contain is_single_color"
            
            assert isinstance(structured_data["dominant_color"], str), "dominant_color should be string"
            assert isinstance(structured_data["confidence"], (int, float)), "confidence should be number"
            assert isinstance(structured_data["is_single_color"], bool), "is_single_color should be boolean"
            
            assert 0 <= structured_data["confidence"] <= 100, "confidence should be 0-100"
            assert "red" in structured_data["dominant_color"].lower() or "#ff0000" in structured_data["dominant_color"].lower(), "Should detect red color"
            
            print("✅ Anthropic structured output integration test passed!")
            
        finally:
            # Cleanup
            providers_module.async_get_clientsession = original_get_session
            await hass.close_session()

    @pytest.mark.asyncio  
    async def test_google_structured_output(self):
        """Test Google structured output through provider implementation"""
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            pytest.skip("GOOGLE_API_KEY not set")
            
        print("🧪 Testing Google structured output via provider implementation...")
        
        # Set up mock hass with provider config
        hass = MockHass()
        provider_uid = setup_provider_config(hass, "Google", api_key, "gemini-1.5-flash")
        
        # Monkey patch to use real session
        import custom_components.llmvision.providers as providers_module
        original_get_session = providers_module.async_get_clientsession
        providers_module.async_get_clientsession = hass.get_real_session
        
        try:
            # Create Request instance
            request = Request(hass, "What is the dominant color in this image?", 100, 0.1)
            # Set images on the request object
            request.base64_images = [create_test_image_base64()]
            request.filenames = ["test_image.png"]
            
            # Define test schema (Google doesn't support additionalProperties)
            color_schema = {
                "type": "object",
                "properties": {
                    "dominant_color": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_single_color": {"type": "boolean"}
                },
                "required": ["dominant_color", "confidence", "is_single_color"]
            }
            
            # Create service call with structured output
            call = MockServiceCall(
                response_format="json",
                structure=json.dumps(color_schema),
                base64_images=[create_test_image_base64()],
                filenames=["test_image.png"],
                message="What is the dominant color in this image? Respond with confidence level and whether it's a single solid color."
            )
            # Add provider to call
            call.provider = provider_uid
            
            # Make actual API call through Request.call()
            response = await request.call(call)
            
            print(f"✅ Provider response: {response}")
            
            # Validate response structure
            assert "response_text" in response, "Response should contain response_text"
            
            # Parse and validate structured output
            structured_data = json.loads(response["response_text"])
            
            # Validate schema compliance
            assert "dominant_color" in structured_data, "Response should contain dominant_color"
            assert "confidence" in structured_data, "Response should contain confidence"  
            assert "is_single_color" in structured_data, "Response should contain is_single_color"
            
            assert isinstance(structured_data["dominant_color"], str), "dominant_color should be string"
            assert isinstance(structured_data["confidence"], (int, float)), "confidence should be number"
            assert isinstance(structured_data["is_single_color"], bool), "is_single_color should be boolean"
            
            assert 0 <= structured_data["confidence"] <= 100, "confidence should be 0-100"
            assert "red" in structured_data["dominant_color"].lower() or "#ff0000" in structured_data["dominant_color"].lower(), "Should detect red color"
            
            print("✅ Google structured output integration test passed!")
            
        finally:
            # Cleanup
            providers_module.async_get_clientsession = original_get_session
            await hass.close_session()

    @pytest.mark.asyncio  
    async def test_ollama_structured_output(self):
        """Test Ollama structured output through provider implementation"""
        ollama_host = os.getenv('OLLAMA_HOST', 'localhost')
        ollama_port = os.getenv('OLLAMA_PORT', '11434')
        
        print("🧪 Testing Ollama structured output via provider implementation...")
        
        # Set up mock hass with provider config - Ollama needs special setup
        hass = MockHass()
        provider_uid = f"test_ollama_config"
        hass.data[DOMAIN][provider_uid] = {
            CONF_PROVIDER: "Ollama",
            CONF_IP_ADDRESS: ollama_host,
            CONF_PORT: ollama_port,
            CONF_HTTPS: False,
            CONF_DEFAULT_MODEL: "llava"
        }
        
        # Monkey patch to use real session
        import custom_components.llmvision.providers as providers_module
        original_get_session = providers_module.async_get_clientsession
        providers_module.async_get_clientsession = hass.get_real_session
        
        try:
            # Create Request instance
            request = Request(hass, "What is the dominant color in this image?", 100, 0.1)
            # Set images on the request object
            request.base64_images = [create_test_image_base64()]
            request.filenames = ["test_image.png"]
            
            # Define test schema
            color_schema = {
                "type": "object",
                "properties": {
                    "dominant_color": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_single_color": {"type": "boolean"}
                },
                "required": ["dominant_color", "confidence", "is_single_color"]
            }
            
            # Create service call with structured output
            call = MockServiceCall(
                response_format="json",
                structure=json.dumps(color_schema),
                base64_images=[create_test_image_base64()],
                filenames=["test_image.png"],
                message="What is the dominant color in this image? Respond with confidence level and whether it's a single solid color."
            )
            # Add provider to call
            call.provider = provider_uid
            
            # Make actual API call through Request.call()
            response = await request.call(call)
            
            print(f"✅ Provider response: {response}")
            
            # Validate response structure
            assert "response_text" in response, "Response should contain response_text"
            
            # Parse and validate structured output
            structured_data = json.loads(response["response_text"])
            
            # Validate schema compliance
            assert "dominant_color" in structured_data, "Response should contain dominant_color"
            assert "confidence" in structured_data, "Response should contain confidence"  
            assert "is_single_color" in structured_data, "Response should contain is_single_color"
            
            assert isinstance(structured_data["dominant_color"], str), "dominant_color should be string"
            assert isinstance(structured_data["confidence"], (int, float)), "confidence should be number"
            assert isinstance(structured_data["is_single_color"], bool), "is_single_color should be boolean"
            
            assert 0 <= structured_data["confidence"] <= 100, "confidence should be 0-100"
            assert "red" in structured_data["dominant_color"].lower() or "#ff0000" in structured_data["dominant_color"].lower(), "Should detect red color"
            
            print("✅ Ollama structured output integration test passed!")
            
        finally:
            # Cleanup
            providers_module.async_get_clientsession = original_get_session
            await hass.close_session()

    @pytest.mark.asyncio
    async def test_azureopenai_structured_output(self):
        """Test AzureOpenAI structured output through provider implementation"""
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-08-01-preview')
        
        if not api_key or not endpoint or not deployment:
            pytest.skip("AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, or AZURE_OPENAI_DEPLOYMENT not set")
            
        print("🧪 Testing AzureOpenAI structured output via provider implementation...")
        
        # Set up mock hass with provider config
        hass = MockHass()
        provider_uid = f"test_azureopenai_config"
        hass.data[DOMAIN][provider_uid] = {
            CONF_PROVIDER: "Azure",
            CONF_API_KEY: api_key,
            CONF_DEFAULT_MODEL: "gpt-4o-mini",
            "azure_base_url": endpoint,
            "azure_deployment": deployment,
            "azure_version": api_version
        }
        
        # Monkey patch to use real session
        import custom_components.llmvision.providers as providers_module
        original_get_session = providers_module.async_get_clientsession
        providers_module.async_get_clientsession = hass.get_real_session
        
        try:
            # Create Request instance
            request = Request(hass, "What is the dominant color in this image?", 100, 0.1)
            request.base64_images = [create_test_image_base64()]
            request.filenames = ["test_image.png"]
            
            # Define test schema
            color_schema = {
                "type": "object",
                "properties": {
                    "dominant_color": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_single_color": {"type": "boolean"}
                },
                "required": ["dominant_color", "confidence", "is_single_color"],
                "additionalProperties": False
            }
            
            # Create service call with structured output
            call = MockServiceCall(
                response_format="json",
                structure=json.dumps(color_schema),
                base64_images=[create_test_image_base64()],
                filenames=["test_image.png"],
                message="What is the dominant color in this image? Respond with confidence level and whether it's a single solid color."
            )
            call.provider = provider_uid
            
            # Make actual API call through Request.call()
            response = await request.call(call)
            
            print(f"✅ Provider response: {response}")
            
            # Validate response structure
            assert "response_text" in response, "Response should contain response_text"
            
            # Parse and validate structured output
            structured_data = json.loads(response["response_text"])
            
            # Validate schema compliance
            assert "dominant_color" in structured_data, "Response should contain dominant_color"
            assert "confidence" in structured_data, "Response should contain confidence"
            assert "is_single_color" in structured_data, "Response should contain is_single_color"
            
            assert isinstance(structured_data["dominant_color"], str), "dominant_color should be string"
            assert isinstance(structured_data["confidence"], (int, float)), "confidence should be number"
            assert isinstance(structured_data["is_single_color"], bool), "is_single_color should be boolean"
            
            assert 0 <= structured_data["confidence"] <= 100, "confidence should be 0-100"
            assert "red" in structured_data["dominant_color"].lower() or "#ff0000" in structured_data["dominant_color"].lower(), "Should detect red color"
            
            print("✅ AzureOpenAI structured output integration test passed!")
            
        finally:
            # Cleanup
            providers_module.async_get_clientsession = original_get_session
            await hass.close_session()

    @pytest.mark.asyncio
    async def test_groq_structured_output(self):
        """Test Groq structured output through provider implementation"""
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            pytest.skip("GROQ_API_KEY not set")
            
        print("🧪 Testing Groq structured output via provider implementation...")
        
        # Set up mock hass with provider config
        hass = MockHass()
        provider_uid = setup_provider_config(hass, "Groq", api_key, "meta-llama/llama-4-maverick-17b-128e-instruct")
        
        # Monkey patch to use real session
        import custom_components.llmvision.providers as providers_module
        original_get_session = providers_module.async_get_clientsession
        providers_module.async_get_clientsession = hass.get_real_session
        
        try:
            # Create Request instance
            request = Request(hass, "What is the dominant color in this image?", 100, 0.1)
            request.base64_images = [create_test_image_base64()]
            request.filenames = ["test_image.png"]
            
            # Define test schema
            color_schema = {
                "type": "object",
                "properties": {
                    "dominant_color": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_single_color": {"type": "boolean"}
                },
                "required": ["dominant_color", "confidence", "is_single_color"]
            }
            
            # Create service call with structured output
            call = MockServiceCall(
                response_format="json",
                structure=json.dumps(color_schema),
                base64_images=[create_test_image_base64()],
                filenames=["test_image.png"],
                message="What is the dominant color in this image? Respond with confidence level and whether it's a single solid color."
            )
            call.provider = provider_uid
            
            # Make actual API call through Request.call()
            response = await request.call(call)
            
            print(f"✅ Provider response: {response}")
            
            # Validate response structure
            assert "response_text" in response, "Response should contain response_text"
            
            # Parse and validate structured output
            structured_data = json.loads(response["response_text"])
            
            # Validate schema compliance
            assert "dominant_color" in structured_data, "Response should contain dominant_color"
            assert "confidence" in structured_data, "Response should contain confidence"
            assert "is_single_color" in structured_data, "Response should contain is_single_color"
            
            assert isinstance(structured_data["dominant_color"], str), "dominant_color should be string"
            assert isinstance(structured_data["confidence"], (int, float)), "confidence should be number"
            assert isinstance(structured_data["is_single_color"], bool), "is_single_color should be boolean"
            
            assert 0 <= structured_data["confidence"] <= 100, "confidence should be 0-100"
            assert "red" in structured_data["dominant_color"].lower() or "#ff0000" in structured_data["dominant_color"].lower(), "Should detect red color"
            
            print("✅ Groq structured output integration test passed!")
            
        finally:
            # Cleanup
            providers_module.async_get_clientsession = original_get_session
            await hass.close_session()

    @pytest.mark.asyncio
    async def test_localai_structured_output(self):
        """Test LocalAI structured output through provider implementation"""
        localai_host = os.getenv('LOCALAI_HOST', 'localhost')
        localai_port = os.getenv('LOCALAI_PORT', '8080')
        
        print("🧪 Testing LocalAI structured output via provider implementation...")
        
        # Set up mock hass with provider config
        hass = MockHass()
        provider_uid = f"test_localai_config"
        hass.data[DOMAIN][provider_uid] = {
            CONF_PROVIDER: "LocalAI",
            CONF_IP_ADDRESS: localai_host,
            CONF_PORT: localai_port,
            CONF_HTTPS: False,
            CONF_DEFAULT_MODEL: "opengvlab_internvl3_5-8b"
        }
        
        # Monkey patch to use real session
        import custom_components.llmvision.providers as providers_module
        original_get_session = providers_module.async_get_clientsession
        providers_module.async_get_clientsession = hass.get_real_session
        
        try:
            # Create Request instance
            request = Request(hass, "What is the dominant color in this image?", 100, 0.1)
            request.base64_images = [create_test_image_base64()]
            request.filenames = ["test_image.png"]
            
            # Define test schema
            color_schema = {
                "type": "object",
                "properties": {
                    "dominant_color": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_single_color": {"type": "boolean"}
                },
                "required": ["dominant_color", "confidence", "is_single_color"]
            }
            
            # Create service call with structured output
            call = MockServiceCall(
                response_format="json",
                structure=json.dumps(color_schema),
                base64_images=[create_test_image_base64()],
                filenames=["test_image.png"],
                message="What is the dominant color in this image? Respond with confidence level and whether it's a single solid color."
            )
            call.provider = provider_uid
            
            # Make actual API call through Request.call()
            response = await request.call(call)
            
            print(f"✅ Provider response: {response}")
            
            # Validate response structure
            assert "response_text" in response, "Response should contain response_text"
            
            # Parse and validate structured output
            structured_data = json.loads(response["response_text"])
            
            # Validate schema compliance
            assert "dominant_color" in structured_data, "Response should contain dominant_color"
            assert "confidence" in structured_data, "Response should contain confidence"
            assert "is_single_color" in structured_data, "Response should contain is_single_color"
            
            assert isinstance(structured_data["dominant_color"], str), "dominant_color should be string"
            assert isinstance(structured_data["confidence"], (int, float)), "confidence should be number"
            assert isinstance(structured_data["is_single_color"], bool), "is_single_color should be boolean"
            
            assert 0 <= structured_data["confidence"] <= 100, "confidence should be 0-100"
            assert "red" in structured_data["dominant_color"].lower() or "#ff0000" in structured_data["dominant_color"].lower(), "Should detect red color"
            
            print("✅ LocalAI structured output integration test passed!")
            
        finally:
            # Cleanup
            providers_module.async_get_clientsession = original_get_session
            await hass.close_session()

    @pytest.mark.asyncio
    async def test_aws_bedrock_structured_output(self):
        """Test AWS Bedrock structured output through provider implementation"""
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not aws_access_key_id or not aws_secret_access_key:
            pytest.skip("AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY not set")
            
        print("🧪 Testing AWS Bedrock structured output via provider implementation...")
        
        # Set up mock hass with provider config
        hass = MockHass()
        provider_uid = f"test_bedrock_config"
        hass.data[DOMAIN][provider_uid] = {
            CONF_PROVIDER: "AWS Bedrock",
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "aws_region_name": aws_region,
            CONF_DEFAULT_MODEL: "us.anthropic.claude-opus-4-1-20250805-v1:0"
        }
        
        # Monkey patch to use real session
        import custom_components.llmvision.providers as providers_module
        original_get_session = providers_module.async_get_clientsession
        providers_module.async_get_clientsession = hass.get_real_session
        
        try:
            # Create Request instance
            request = Request(hass, "What is the dominant color in this image?", 100, 0.1)
            request.base64_images = [create_test_image_base64()]
            request.filenames = ["test_image.png"]
            
            # Define test schema
            color_schema = {
                "type": "object",
                "properties": {
                    "dominant_color": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_single_color": {"type": "boolean"}
                },
                "required": ["dominant_color", "confidence", "is_single_color"]
            }
            
            # Create service call with structured output
            call = MockServiceCall(
                response_format="json",
                structure=json.dumps(color_schema),
                base64_images=[create_test_image_base64()],
                filenames=["test_image.png"],
                message="What is the dominant color in this image? Respond with confidence level and whether it's a single solid color."
            )
            call.provider = provider_uid
            
            # Make actual API call through Request.call()
            response = await request.call(call)
            
            print(f"✅ Provider response: {response}")
            
            # Validate response structure
            assert "response_text" in response, "Response should contain response_text"
            
            # Parse and validate structured output
            structured_data = json.loads(response["response_text"])
            
            # Validate schema compliance
            assert "dominant_color" in structured_data, "Response should contain dominant_color"
            assert "confidence" in structured_data, "Response should contain confidence"
            assert "is_single_color" in structured_data, "Response should contain is_single_color"
            
            assert isinstance(structured_data["dominant_color"], str), "dominant_color should be string"
            assert isinstance(structured_data["confidence"], (int, float)), "confidence should be number"
            assert isinstance(structured_data["is_single_color"], bool), "is_single_color should be boolean"
            
            assert 0 <= structured_data["confidence"] <= 100, "confidence should be 0-100"
            assert "red" in structured_data["dominant_color"].lower() or "#ff0000" in structured_data["dominant_color"].lower(), "Should detect red color"
            
            print("✅ AWS Bedrock structured output integration test passed!")
            
        finally:
            # Cleanup
            providers_module.async_get_clientsession = original_get_session
            await hass.close_session()


if __name__ == "__main__":
    # Run specific provider test
    import sys
    if len(sys.argv) > 1:
        provider = sys.argv[1].lower()
        test_instance = TestStructuredOutputIntegration()
        if provider == "openai":
            asyncio.run(test_instance.test_openai_structured_output())
        elif provider == "anthropic":
            asyncio.run(test_instance.test_anthropic_structured_output())
        elif provider == "google":
            asyncio.run(test_instance.test_google_structured_output())
        elif provider == "ollama":
            asyncio.run(test_instance.test_ollama_structured_output())
        elif provider == "azureopenai":
            asyncio.run(test_instance.test_azureopenai_structured_output())
        elif provider == "groq":
            asyncio.run(test_instance.test_groq_structured_output())
        elif provider == "localai":
            asyncio.run(test_instance.test_localai_structured_output())
        elif provider == "bedrock" or provider == "aws":
            asyncio.run(test_instance.test_aws_bedrock_structured_output())
        else:
            print("Usage: python test_structured_output_integration.py [openai|anthropic|google|ollama|azureopenai|groq|localai|bedrock]")
    else:
        print("Usage: python test_structured_output_integration.py [openai|anthropic|google|ollama|azureopenai|groq|localai|bedrock]")