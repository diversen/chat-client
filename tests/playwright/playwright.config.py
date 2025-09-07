# playwright.config.py
"""Playwright configuration for chat-client tests."""
from playwright.sync_api import Playwright


def run(playwright: Playwright) -> None:
    """Configure Playwright for testing."""
    # Browser configurations
    browser = playwright.chromium.launch(
        headless=True,
        slow_mo=50,  # Slow down operations by 50ms for stability
    )
    
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
        # Record video on failure
        record_video_dir="tests/playwright/videos/",
        record_video_size={"width": 1280, "height": 720},
    )
    
    return context


# Configuration for pytest-playwright
def pytest_configure(config):
    """Configure pytest for Playwright tests."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "auth: marks tests requiring authentication") 
    config.addinivalue_line("markers", "ui: marks tests for UI interactions")
    config.addinivalue_line("markers", "chat: marks tests for chat functionality")


# Pytest fixtures configuration
pytest_plugins = ["pytest_playwright"]