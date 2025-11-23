"""Unit tests for const.py module."""
import pytest
from custom_components.llmvision.const import (
    DOMAIN,
    CONF_PROVIDER,
    CONF_API_KEY,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TITLE_PROMPT,
    DEFAULT_OPENAI_MODEL,
    ERROR_NOT_CONFIGURED,
    ERROR_NO_IMAGE_INPUT,
    ENDPOINT_OPENAI,
    VERSION_ANTHROPIC,
)


class TestConstants:
    """Test constants are properly defined."""

    def test_domain(self):
        """Test DOMAIN constant."""
        assert DOMAIN == "llmvision"

    def test_config_keys(self):
        """Test configuration key constants."""
        assert CONF_PROVIDER == "provider"
        assert CONF_API_KEY == "api_key"

    def test_default_prompts(self):
        """Test default prompt constants."""
        assert isinstance(DEFAULT_SYSTEM_PROMPT, str)
        assert len(DEFAULT_SYSTEM_PROMPT) > 0
        assert isinstance(DEFAULT_TITLE_PROMPT, str)
        assert len(DEFAULT_TITLE_PROMPT) > 0

    def test_default_models(self):
        """Test default model constants."""
        assert DEFAULT_OPENAI_MODEL == "gpt-4o-mini"

    def test_error_messages(self):
        """Test error message constants."""
        assert "{provider}" in ERROR_NOT_CONFIGURED
        assert isinstance(ERROR_NO_IMAGE_INPUT, str)

    def test_endpoints(self):
        """Test API endpoint constants."""
        assert ENDPOINT_OPENAI.startswith("https://")
        assert "openai.com" in ENDPOINT_OPENAI

    def test_versions(self):
        """Test version constants."""
        assert isinstance(VERSION_ANTHROPIC, str)
        assert len(VERSION_ANTHROPIC) > 0



class TestServiceCallConstants:
    """Test service call constants."""

    def test_message_constant(self):
        """Test MESSAGE constant."""
        from custom_components.llmvision.const import MESSAGE
        assert MESSAGE == "message"

    def test_store_in_timeline_constant(self):
        """Test STORE_IN_TIMELINE constant."""
        from custom_components.llmvision.const import STORE_IN_TIMELINE
        assert STORE_IN_TIMELINE == "store_in_timeline"

    def test_use_memory_constant(self):
        """Test USE_MEMORY constant."""
        from custom_components.llmvision.const import USE_MEMORY
        assert USE_MEMORY == "use_memory"

    def test_provider_constant(self):
        """Test PROVIDER constant."""
        from custom_components.llmvision.const import PROVIDER
        assert PROVIDER == "provider"

    def test_model_constant(self):
        """Test MODEL constant."""
        from custom_components.llmvision.const import MODEL
        assert MODEL == "model"


class TestConfigConstants:
    """Test configuration constants."""

    def test_conf_ip_address(self):
        """Test CONF_IP_ADDRESS constant."""
        from custom_components.llmvision.const import CONF_IP_ADDRESS
        assert CONF_IP_ADDRESS == "ip_address"

    def test_conf_port(self):
        """Test CONF_PORT constant."""
        from custom_components.llmvision.const import CONF_PORT
        assert CONF_PORT == "port"

    def test_conf_https(self):
        """Test CONF_HTTPS constant."""
        from custom_components.llmvision.const import CONF_HTTPS
        assert CONF_HTTPS == "https"

    def test_conf_temperature(self):
        """Test CONF_TEMPERATURE constant."""
        from custom_components.llmvision.const import CONF_TEMPERATURE
        assert CONF_TEMPERATURE == "temperature"

    def test_conf_top_p(self):
        """Test CONF_TOP_P constant."""
        from custom_components.llmvision.const import CONF_TOP_P
        assert CONF_TOP_P == "top_p"


class TestAzureConstants:
    """Test Azure-specific constants."""

    def test_conf_azure_base_url(self):
        """Test CONF_AZURE_BASE_URL constant."""
        from custom_components.llmvision.const import CONF_AZURE_BASE_URL
        assert CONF_AZURE_BASE_URL == "azure_base_url"

    def test_conf_azure_deployment(self):
        """Test CONF_AZURE_DEPLOYMENT constant."""
        from custom_components.llmvision.const import CONF_AZURE_DEPLOYMENT
        assert CONF_AZURE_DEPLOYMENT == "azure_deployment"

    def test_conf_azure_version(self):
        """Test CONF_AZURE_VERSION constant."""
        from custom_components.llmvision.const import CONF_AZURE_VERSION
        assert CONF_AZURE_VERSION == "azure_version"


class TestAWSConstants:
    """Test AWS-specific constants."""

    def test_conf_aws_access_key_id(self):
        """Test CONF_AWS_ACCESS_KEY_ID constant."""
        from custom_components.llmvision.const import CONF_AWS_ACCESS_KEY_ID
        assert CONF_AWS_ACCESS_KEY_ID == "aws_access_key_id"

    def test_conf_aws_secret_access_key(self):
        """Test CONF_AWS_SECRET_ACCESS_KEY constant."""
        from custom_components.llmvision.const import CONF_AWS_SECRET_ACCESS_KEY
        assert CONF_AWS_SECRET_ACCESS_KEY == "aws_secret_access_key"

    def test_conf_aws_region_name(self):
        """Test CONF_AWS_REGION_NAME constant."""
        from custom_components.llmvision.const import CONF_AWS_REGION_NAME
        assert CONF_AWS_REGION_NAME == "aws_region_name"


class TestModelDefaults:
    """Test default model constants."""

    def test_default_anthropic_model(self):
        """Test DEFAULT_ANTHROPIC_MODEL constant."""
        from custom_components.llmvision.const import DEFAULT_ANTHROPIC_MODEL
        assert isinstance(DEFAULT_ANTHROPIC_MODEL, str)
        assert "claude" in DEFAULT_ANTHROPIC_MODEL.lower()

    def test_default_azure_model(self):
        """Test DEFAULT_AZURE_MODEL constant."""
        from custom_components.llmvision.const import DEFAULT_AZURE_MODEL
        assert DEFAULT_AZURE_MODEL == "gpt-4o-mini"

    def test_default_google_model(self):
        """Test DEFAULT_GOOGLE_MODEL constant."""
        from custom_components.llmvision.const import DEFAULT_GOOGLE_MODEL
        assert isinstance(DEFAULT_GOOGLE_MODEL, str)
        assert "gemini" in DEFAULT_GOOGLE_MODEL.lower()

    def test_default_groq_model(self):
        """Test DEFAULT_GROQ_MODEL constant."""
        from custom_components.llmvision.const import DEFAULT_GROQ_MODEL
        assert isinstance(DEFAULT_GROQ_MODEL, str)

    def test_default_localai_model(self):
        """Test DEFAULT_LOCALAI_MODEL constant."""
        from custom_components.llmvision.const import DEFAULT_LOCALAI_MODEL
        assert DEFAULT_LOCALAI_MODEL == "llava"

    def test_default_ollama_model(self):
        """Test DEFAULT_OLLAMA_MODEL constant."""
        from custom_components.llmvision.const import DEFAULT_OLLAMA_MODEL
        assert isinstance(DEFAULT_OLLAMA_MODEL, str)

    def test_default_aws_model(self):
        """Test DEFAULT_AWS_MODEL constant."""
        from custom_components.llmvision.const import DEFAULT_AWS_MODEL
        assert isinstance(DEFAULT_AWS_MODEL, str)


class TestEndpointConstants:
    """Test API endpoint constants."""

    def test_endpoint_anthropic(self):
        """Test ENDPOINT_ANTHROPIC constant."""
        from custom_components.llmvision.const import ENDPOINT_ANTHROPIC
        assert ENDPOINT_ANTHROPIC.startswith("https://")
        assert "anthropic.com" in ENDPOINT_ANTHROPIC

    def test_endpoint_google(self):
        """Test ENDPOINT_GOOGLE constant."""
        from custom_components.llmvision.const import ENDPOINT_GOOGLE
        assert ENDPOINT_GOOGLE.startswith("https://")
        assert "googleapis.com" in ENDPOINT_GOOGLE

    def test_endpoint_groq(self):
        """Test ENDPOINT_GROQ constant."""
        from custom_components.llmvision.const import ENDPOINT_GROQ
        assert ENDPOINT_GROQ.startswith("https://")
        assert "groq.com" in ENDPOINT_GROQ

    def test_endpoint_localai(self):
        """Test ENDPOINT_LOCALAI constant."""
        from custom_components.llmvision.const import ENDPOINT_LOCALAI
        assert "{protocol}" in ENDPOINT_LOCALAI
        assert "{ip_address}" in ENDPOINT_LOCALAI

    def test_endpoint_ollama(self):
        """Test ENDPOINT_OLLAMA constant."""
        from custom_components.llmvision.const import ENDPOINT_OLLAMA
        assert "{protocol}" in ENDPOINT_OLLAMA
        assert "{ip_address}" in ENDPOINT_OLLAMA

    def test_endpoint_azure(self):
        """Test ENDPOINT_AZURE constant."""
        from custom_components.llmvision.const import ENDPOINT_AZURE
        assert "{base_url}" in ENDPOINT_AZURE
        assert "{deployment}" in ENDPOINT_AZURE


class TestVersionConstants:
    """Test version constants."""

    def test_version_azure(self):
        """Test VERSION_AZURE constant."""
        from custom_components.llmvision.const import VERSION_AZURE
        assert isinstance(VERSION_AZURE, str)
        assert len(VERSION_AZURE) > 0


class TestPromptConstants:
    """Test prompt constants."""

    def test_data_extraction_prompt(self):
        """Test DATA_EXTRACTION_PROMPT constant."""
        from custom_components.llmvision.const import DATA_EXTRACTION_PROMPT
        assert isinstance(DATA_EXTRACTION_PROMPT, str)
        assert len(DATA_EXTRACTION_PROMPT) > 0

    def test_default_summary_prompt(self):
        """Test DEFAULT_SUMMARY_PROMPT constant."""
        from custom_components.llmvision.const import DEFAULT_SUMMARY_PROMPT
        assert isinstance(DEFAULT_SUMMARY_PROMPT, str)
        assert len(DEFAULT_SUMMARY_PROMPT) > 0
