"""Authentication flow tests for the chat-client frontend."""
import pytest
from playwright.async_api import Page, expect


class TestAuthentication:
    """Test user authentication workflows."""

    async def test_login_page_loads(self, page: Page, test_server):
        """Test that the login page loads correctly."""
        await page.goto(f"{test_server}/user/login")
        
        # Check page title and main elements
        await expect(page).to_have_title("Login - chat-client")
        await expect(page.locator("h3")).to_contain_text("Login")
        
        # Check form elements exist
        await expect(page.locator("#email")).to_be_visible()
        await expect(page.locator("#password")).to_be_visible()
        await expect(page.locator("#remember")).to_be_visible()
        await expect(page.locator("#login")).to_be_visible()
        
        # Check password reset link
        await expect(page.locator('a[href="/user/reset"]')).to_contain_text("Reset your password")

    async def test_successful_login(self, page: Page, test_server):
        """Test successful user login."""
        await page.goto(f"{test_server}/user/login")
        
        # Fill in login form
        await page.fill("#email", "test@example.com")
        await page.fill("#password", "test123456")
        await page.check("#remember")  # Check remember me
        
        # Submit form
        await page.click("#login")
        
        # Should redirect to home page
        await page.wait_for_url(f"{test_server}/")
        
        # Check that we're logged in (navigation should show user menu)
        await expect(page.locator("nav")).to_be_visible()
        await expect(page.locator("#new")).to_be_visible()  # New conversation button

    async def test_login_with_wrong_password(self, page: Page, test_server):
        """Test login with incorrect password."""
        await page.goto(f"{test_server}/user/login")
        
        # Fill in login form with wrong password
        await page.fill("#email", "test@example.com")
        await page.fill("#password", "wrongpassword")
        
        # Submit form
        await page.click("#login")
        
        # Should stay on login page and show error
        await expect(page.locator(".flash-message.error, .error-message")).to_be_visible()

    async def test_login_with_nonexistent_user(self, page: Page, test_server):
        """Test login with non-existent email."""
        await page.goto(f"{test_server}/user/login")
        
        # Fill in login form with non-existent email
        await page.fill("#email", "nonexistent@example.com")
        await page.fill("#password", "somepassword")
        
        # Submit form
        await page.click("#login")
        
        # Should stay on login page and show error
        await expect(page.locator(".flash-message.error, .error-message")).to_be_visible()

    async def test_empty_login_form(self, page: Page, test_server):
        """Test submitting empty login form."""
        await page.goto(f"{test_server}/user/login")
        
        # Submit empty form
        await page.click("#login")
        
        # Should show validation errors or stay on page
        current_url = page.url
        assert "/user/login" in current_url

    async def test_signup_page_loads(self, page: Page, test_server):
        """Test that the signup page loads correctly."""
        await page.goto(f"{test_server}/user/signup")
        
        # Check page title and main elements
        await expect(page).to_have_title("Sign up - chat-client")
        await expect(page.locator("h3")).to_contain_text("Sign up")
        
        # Check form elements exist
        await expect(page.locator('input[name="email"]')).to_be_visible()
        await expect(page.locator('input[name="password"]')).to_be_visible()
        await expect(page.locator('input[name="password2"]')).to_be_visible()

    async def test_already_logged_in_redirect(self, authenticated_page: Page, test_server):
        """Test that already logged in users are redirected appropriately."""
        # Try to visit login page while already logged in
        await authenticated_page.goto(f"{test_server}/user/login")
        
        # Should show message that user is already logged in
        await expect(authenticated_page.locator("p")).to_contain_text("You are already logged in")

    async def test_logout_functionality(self, authenticated_page: Page, test_server):
        """Test user logout."""
        # Should be on home page and authenticated
        await expect(authenticated_page.locator("#new")).to_be_visible()
        
        # Go to logout
        await authenticated_page.goto(f"{test_server}/user/logout")
        
        # Should redirect to login page or show logged out message
        await authenticated_page.wait_for_timeout(1000)  # Wait for redirect
        
        # Check we're no longer authenticated by visiting home page
        await authenticated_page.goto(f"{test_server}/")
        
        # Should redirect to login or show login prompt
        current_url = authenticated_page.url
        assert "/user/login" in current_url or "login" in await authenticated_page.content()

    async def test_navigation_when_not_logged_in(self, page: Page, test_server):
        """Test navigation redirects when not logged in."""
        # Try to access home page without being logged in
        await page.goto(f"{test_server}/")
        
        # Should redirect to login page
        await page.wait_for_timeout(1000)
        current_url = page.url
        assert "/user/login" in current_url

    async def test_remember_me_checkbox(self, page: Page, test_server):
        """Test remember me checkbox functionality."""
        await page.goto(f"{test_server}/user/login")
        
        # Check that remember me is checked by default
        await expect(page.locator("#remember")).to_be_checked()
        
        # Uncheck it
        await page.uncheck("#remember")
        await expect(page.locator("#remember")).not_to_be_checked()
        
        # Check it again
        await page.check("#remember")
        await expect(page.locator("#remember")).to_be_checked()

    async def test_form_validation(self, page: Page, test_server):
        """Test client-side form validation."""
        await page.goto(f"{test_server}/user/login")
        
        # Test email field validation (if implemented)
        await page.fill("#email", "invalid-email")
        await page.fill("#password", "test123")
        
        # The form should handle validation appropriately
        # This test might need adjustment based on actual validation implementation
        await page.click("#login")
        
        # Check that form handles invalid email appropriately
        # (This test is more about ensuring the form doesn't crash)
        await expect(page.locator("#email")).to_be_visible()

    async def test_ui_responsiveness(self, page: Page, test_server):
        """Test that login page is responsive."""
        await page.goto(f"{test_server}/user/login")
        
        # Test mobile viewport
        await page.set_viewport_size({"width": 375, "height": 667})
        await expect(page.locator("form")).to_be_visible()
        await expect(page.locator("#email")).to_be_visible()
        
        # Test desktop viewport
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await expect(page.locator("form")).to_be_visible()
        await expect(page.locator("#email")).to_be_visible()

    async def test_theme_consistency(self, page: Page, test_server):
        """Test that theme elements are present on login page."""
        await page.goto(f"{test_server}/user/login")
        
        # Check for theme-related CSS classes or elements
        # This ensures the page integrates with the app's theming system
        body = page.locator("body")
        await expect(body).to_be_visible()
        
        # Check for navigation elements that might contain theme switcher
        nav = page.locator("nav")
        if await nav.count() > 0:
            await expect(nav).to_be_visible()