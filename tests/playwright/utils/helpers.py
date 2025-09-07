"""Test utilities and helpers for Playwright tests."""
from pathlib import Path
import asyncio
import tempfile
import sqlite3
import bcrypt
from typing import Dict, Any


class TestDatabase:
    """Helper for managing test database."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def create_user(self, email: str, password: str, verified: bool = True) -> int:
        """Create a test user and return user ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Insert user
        cursor.execute("""
            INSERT INTO users (email, password, verified, created_on) 
            VALUES (?, ?, ?, datetime('now'))
        """, (email, password_hash, 1 if verified else 0))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return user_id
    
    def delete_user(self, email: str):
        """Delete a test user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email = ?", (email,))
        conn.commit()
        conn.close()
    
    def cleanup(self):
        """Clean up test data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clean up test users (keep only essential test user)
        cursor.execute("DELETE FROM users WHERE email != 'test@example.com'")
        
        # Clean up chat history
        cursor.execute("DELETE FROM chats")
        cursor.execute("DELETE FROM messages")
        
        conn.commit()
        conn.close()


class UIHelpers:
    """Helper methods for UI testing."""
    
    @staticmethod
    async def wait_for_page_load(page, timeout: int = 5000):
        """Wait for page to fully load."""
        await page.wait_for_load_state("networkidle", timeout=timeout)
    
    @staticmethod
    async def fill_login_form(page, email: str, password: str, remember: bool = True):
        """Fill and submit login form."""
        await page.fill("#email", email)
        await page.fill("#password", password)
        
        if remember:
            await page.check("#remember")
        else:
            await page.uncheck("#remember")
        
        await page.click("#login")
    
    @staticmethod
    async def send_chat_message(page, message: str):
        """Send a chat message."""
        await page.fill("#message", message)
        await page.click("#send")
    
    @staticmethod
    async def wait_for_chat_response(page, timeout: int = 10000):
        """Wait for chat response to appear."""
        # This would need to be implemented based on how responses appear
        await page.wait_for_timeout(1000)  # Basic wait
    
    @staticmethod
    async def check_no_javascript_errors(page) -> list:
        """Check for JavaScript errors on the page."""
        errors = []
        
        def handle_console(msg):
            if msg.type == "error":
                errors.append(msg.text)
        
        page.on("console", handle_console)
        await page.wait_for_timeout(1000)
        page.remove_listener("console", handle_console)
        
        return errors
    
    @staticmethod
    async def take_screenshot_on_failure(page, test_name: str):
        """Take screenshot when test fails."""
        screenshot_dir = Path("tests/playwright/screenshots")
        screenshot_dir.mkdir(exist_ok=True)
        
        screenshot_path = screenshot_dir / f"{test_name}_failure.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        
        return screenshot_path


class TestServer:
    """Helper for managing test server."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def url(self, path: str = "") -> str:
        """Get full URL for a path."""
        return f"{self.base_url}{path}"
    
    def login_url(self) -> str:
        """Get login URL."""
        return self.url("/user/login")
    
    def signup_url(self) -> str:
        """Get signup URL."""
        return self.url("/user/signup")
    
    def home_url(self) -> str:
        """Get home URL."""
        return self.url("/")
    
    def logout_url(self) -> str:
        """Get logout URL."""
        return self.url("/user/logout")


class MockData:
    """Mock data for testing."""
    
    TEST_USER = {
        "email": "test@example.com",
        "password": "test123456"
    }
    
    TEST_USER_2 = {
        "email": "test2@example.com", 
        "password": "test789012"
    }
    
    SAMPLE_MESSAGES = [
        "Hello, how are you?",
        "What is the weather like today?",
        "Can you help me with a coding problem?",
        "Tell me a joke",
        "What is 2 + 2?",
    ]
    
    SAMPLE_RESPONSES = [
        "I'm doing well, thank you for asking!",
        "I don't have access to current weather data.",
        "I'd be happy to help with your coding problem.",
        "Why don't scientists trust atoms? Because they make up everything!",
        "2 + 2 equals 4.",
    ]


class Assertions:
    """Custom assertion helpers."""
    
    @staticmethod
    async def assert_user_logged_in(page):
        """Assert that user is logged in."""
        from playwright.async_api import expect
        
        # Check for elements that should be present when logged in
        await expect(page.locator("#new")).to_be_visible()  # New conversation button
        
        # Check that we're not on login page
        current_url = page.url
        assert "/user/login" not in current_url
    
    @staticmethod
    async def assert_user_logged_out(page):
        """Assert that user is logged out."""
        from playwright.async_api import expect
        
        # Should not have authenticated elements
        new_button = page.locator("#new")
        if await new_button.count() > 0:
            await expect(new_button).not_to_be_visible()
    
    @staticmethod
    async def assert_on_page(page, expected_path: str):
        """Assert that page is on expected path."""
        current_url = page.url
        assert expected_path in current_url
    
    @staticmethod
    async def assert_form_error(page, error_message: str = None):
        """Assert that form shows error."""
        from playwright.async_api import expect
        
        error_element = page.locator(".error, .flash-error, .error-message")
        await expect(error_element).to_be_visible()
        
        if error_message:
            await expect(error_element).to_contain_text(error_message)