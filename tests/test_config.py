"""
Test configuration for Starlette backend tests.
This module provides test configuration and fixtures for testing the backend.
"""
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
import logging


# Test configuration to replace data.config during tests
class TestConfig:
    # SMTP - Mock configuration
    class ConfigSMTP:
        HOST = "smtp.example.com"
        PORT = 587
        USERNAME = "test@example.com"
        PASSWORD = "testpassword"
        DEFAULT_FROM = "Test Chat <test@example.com>"

    # Disable model discovery for tests
    DEFAULT_MODEL = "test-model"

    # Logging
    LOG_LEVEL = logging.WARNING

    # Disable reloading for tests
    RELOAD = False

    # Use temporary directory for test database
    DATA_DIR = tempfile.mkdtemp()
    DATABASE = Path(DATA_DIR) / Path("test_database.db")

    # Test site configuration
    HOSTNAME_WITH_SCHEME = "http://localhost:8000"
    SITE_NAME = "localhost:8000"

    # Test session key
    SESSION_SECRET_KEY = "test-secret-key-for-testing-only-not-secure"

    # Disable HTTPS for tests
    SESSION_HTTPS_ONLY = False

    # Disable KaTeX for tests
    USE_KATEX = False

    # Mock providers - no real API calls
    PROVIDERS = {
        "test-provider": {
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-api-key",
        },
    }

    # Test models
    MODELS = {
        "test-model": "test-provider",
        "tool-model": "test-provider",
    }

    # Mock tool models
    TOOL_MODELS = ["tool-model"]

    # Mock tool registry
    TOOL_REGISTRY = {}

    # Mock tools
    TOOLS = []

    # Mock tools callback
    TOOLS_CALLBACK = {}


def get_test_config():
    """Get test configuration instance"""
    return TestConfig()


def mock_config():
    """Context manager to mock the data.config module with test configuration"""
    test_config = get_test_config()
    return patch.dict('sys.modules', {'data.config': test_config})