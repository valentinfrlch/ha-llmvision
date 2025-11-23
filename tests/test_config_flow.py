"""Unit tests for config_flow.py module."""
import pytest
from unittest.mock import Mock, patch
from custom_components.llmvision.config_flow import llmvisionConfigFlow, flatten_dict


class TestConfigFlow:
    """Test llmvisionConfigFlow class."""

    def test_init(self):
        """Test llmvisionConfigFlow initialization."""
        flow = llmvisionConfigFlow()
        
        assert flow.VERSION == 4
        assert flow.MINOR_VERSION == 0


class TestFlattenDict:
    """Test flatten_dict function."""

    def test_flatten_dict_simple(self):
        """Test flatten_dict with simple nested dict."""
        nested = {
            "section1": {
                "key1": "value1",
                "key2": "value2"
            }
        }
        
        result = flatten_dict(nested)
        
        assert result == {"key1": "value1", "key2": "value2"}

    def test_flatten_dict_multiple_sections(self):
        """Test flatten_dict with multiple sections."""
        nested = {
            "section1": {
                "key1": "value1"
            },
            "section2": {
                "key2": "value2"
            }
        }
        
        result = flatten_dict(nested)
        
        assert result == {"key1": "value1", "key2": "value2"}

    def test_flatten_dict_empty(self):
        """Test flatten_dict with empty dict."""
        result = flatten_dict({})
        
        assert result == {}

    def test_flatten_dict_no_nesting(self):
        """Test flatten_dict with flat dict."""
        flat = {"key1": "value1", "key2": "value2"}
        
        result = flatten_dict(flat)
        
        assert result == flat
