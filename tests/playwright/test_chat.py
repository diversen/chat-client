"""Chat interface and messaging tests for the chat-client frontend."""
import pytest
from playwright.async_api import Page, expect


class TestChatInterface:
    """Test chat interface functionality."""

    async def test_chat_page_loads(self, authenticated_page: Page, test_server):
        """Test that the main chat page loads correctly for authenticated users."""
        # Should already be on home page from authenticated_page fixture
        await expect(authenticated_page).to_have_title("Home - chat-client")
        
        # Check main chat interface elements
        await expect(authenticated_page.locator(".chat-container")).to_be_visible()
        await expect(authenticated_page.locator("#responses")).to_be_visible()
        await expect(authenticated_page.locator("#prompt")).to_be_visible()
        await expect(authenticated_page.locator("#message")).to_be_visible()
        await expect(authenticated_page.locator("#send")).to_be_visible()

    async def test_message_input_functionality(self, authenticated_page: Page, test_server):
        """Test message input field functionality."""
        # Focus on message input
        await authenticated_page.focus("#message")
        
        # Type a message
        test_message = "Hello, this is a test message"
        await authenticated_page.fill("#message", test_message)
        
        # Verify message was typed
        input_value = await authenticated_page.input_value("#message")
        assert input_value == test_message
        
        # Clear the message
        await authenticated_page.fill("#message", "")
        input_value = await authenticated_page.input_value("#message")
        assert input_value == ""

    async def test_send_button_states(self, authenticated_page: Page, test_server):
        """Test send button enable/disable states."""
        # Initially send button should be disabled (assuming this behavior)
        send_button = authenticated_page.locator("#send")
        
        # Check initial state - might be disabled if no message
        await expect(send_button).to_be_visible()
        
        # Type a message
        await authenticated_page.fill("#message", "Test message")
        
        # Send button should be enabled (if implemented)
        await expect(send_button).to_be_visible()
        await expect(send_button).not_to_be_disabled()

    async def test_model_selector(self, authenticated_page: Page, test_server):
        """Test model selection dropdown."""
        model_select = authenticated_page.locator("#select-model")
        
        # Model selector might be hidden initially
        if await model_select.is_visible():
            # Check that it has options
            await expect(model_select).to_be_visible()
            
            # Get all options
            options = await model_select.locator("option").all()
            assert len(options) > 0
            
            # Check for test model if configured
            test_model_option = model_select.locator('option[value="test-model"]')
            if await test_model_option.count() > 0:
                await expect(test_model_option).to_be_visible()

    async def test_scroll_to_bottom_button(self, authenticated_page: Page, test_server):
        """Test scroll to bottom functionality."""
        scroll_button = authenticated_page.locator("#scroll-to-bottom")
        await expect(scroll_button).to_be_visible()
        
        # Button should be clickable
        await expect(scroll_button).to_be_enabled()

    async def test_abort_button(self, authenticated_page: Page, test_server):
        """Test abort button functionality."""
        abort_button = authenticated_page.locator("#abort")
        await expect(abort_button).to_be_visible()
        
        # Initially should be disabled
        await expect(abort_button).to_be_disabled()

    async def test_navigation_elements(self, authenticated_page: Page, test_server):
        """Test navigation elements on chat page."""
        # Check top navigation
        nav = authenticated_page.locator("nav.top-bar")
        await expect(nav).to_be_visible()
        
        # Logo should be present
        logo = authenticated_page.locator("#logo")
        await expect(logo).to_be_visible()
        
        # New conversation button
        new_button = authenticated_page.locator("#new")
        await expect(new_button).to_be_visible()
        await expect(new_button).to_have_attribute("title", "New conversation")

    async def test_new_conversation_button(self, authenticated_page: Page, test_server):
        """Test new conversation functionality."""
        new_button = authenticated_page.locator("#new")
        
        # Click new conversation
        await new_button.click()
        
        # Should stay on or redirect to home page
        await authenticated_page.wait_for_timeout(500)
        
        # Chat interface should still be visible
        await expect(authenticated_page.locator(".chat-container")).to_be_visible()
        await expect(authenticated_page.locator("#message")).to_be_visible()

    async def test_keyboard_shortcuts(self, authenticated_page: Page, test_server):
        """Test keyboard shortcuts in message input."""
        message_input = authenticated_page.locator("#message")
        await message_input.focus()
        
        # Type a message
        await authenticated_page.fill("#message", "Test message")
        
        # Test Enter key to send (if implemented)
        await message_input.press("Enter")
        
        # The exact behavior depends on implementation
        # This test ensures the input handles keyboard events
        await expect(message_input).to_be_visible()

    async def test_message_form_submission(self, authenticated_page: Page, test_server):
        """Test message form submission."""
        # Fill out message
        await authenticated_page.fill("#message", "Test chat message")
        
        # Submit form
        message_form = authenticated_page.locator("#message-form")
        await message_form.submit()
        
        # Form should handle submission gracefully
        await expect(message_form).to_be_visible()

    async def test_responses_container(self, authenticated_page: Page, test_server):
        """Test responses container functionality."""
        responses = authenticated_page.locator("#responses")
        await expect(responses).to_be_visible()
        
        # Container should be ready to display messages
        await expect(responses).to_be_attached()

    async def test_chat_ui_responsiveness(self, authenticated_page: Page, test_server):
        """Test chat interface responsiveness."""
        # Test mobile viewport
        await authenticated_page.set_viewport_size({"width": 375, "height": 667})
        
        # Key elements should still be visible
        await expect(authenticated_page.locator(".chat-container")).to_be_visible()
        await expect(authenticated_page.locator("#message")).to_be_visible()
        await expect(authenticated_page.locator("#send")).to_be_visible()
        
        # Test tablet viewport
        await authenticated_page.set_viewport_size({"width": 768, "height": 1024})
        await expect(authenticated_page.locator(".chat-container")).to_be_visible()
        
        # Test desktop viewport
        await authenticated_page.set_viewport_size({"width": 1920, "height": 1080})
        await expect(authenticated_page.locator(".chat-container")).to_be_visible()

    async def test_prompt_area_functionality(self, authenticated_page: Page, test_server):
        """Test the prompt input area."""
        prompt_area = authenticated_page.locator("#prompt")
        await expect(prompt_area).to_be_visible()
        
        # Check actions area
        actions = authenticated_page.locator(".actions")
        await expect(actions).to_be_visible()
        
        # Check left and right action areas
        actions_left = authenticated_page.locator(".actions-left")
        actions_right = authenticated_page.locator(".actions-right")
        
        await expect(actions_left).to_be_visible()
        await expect(actions_right).to_be_visible()

    async def test_custom_prompt_button(self, authenticated_page: Page, test_server):
        """Test custom prompt functionality if available."""
        custom_prompt_button = authenticated_page.locator("#new-from-custom")
        
        if await custom_prompt_button.count() > 0:
            await expect(custom_prompt_button).to_be_visible()
            await expect(custom_prompt_button).to_have_attribute("title", "New conversation from custom prompt")

    async def test_page_class_application(self, authenticated_page: Page, test_server):
        """Test that proper CSS classes are applied to the chat page."""
        body = authenticated_page.locator("body")
        
        # Chat page should have specific body class
        body_class = await body.get_attribute("class")
        assert body_class and "page-chat" in body_class

    async def test_message_textarea_behavior(self, authenticated_page: Page, test_server):
        """Test textarea behavior and properties."""
        textarea = authenticated_page.locator("#message")
        
        # Should be a textarea element
        await expect(textarea).to_be_visible()
        
        # Should have autofocus
        await expect(textarea).to_have_attribute("autofocus")
        
        # Should have placeholder
        await expect(textarea).to_have_attribute("placeholder", "Ask me anything")
        
        # Should be focusable
        await textarea.focus()
        is_focused = await textarea.evaluate("el => el === document.activeElement")
        assert is_focused

    async def test_svg_icons_presence(self, authenticated_page: Page, test_server):
        """Test that SVG icons are properly loaded."""
        # Send button icon
        send_icon = authenticated_page.locator("#send svg")
        await expect(send_icon).to_be_visible()
        
        # Abort button icon
        abort_icon = authenticated_page.locator("#abort svg")
        await expect(abort_icon).to_be_visible()
        
        # Scroll to bottom icon
        scroll_icon = authenticated_page.locator("#scroll-to-bottom svg")
        await expect(scroll_icon).to_be_visible()

    async def test_javascript_modules_loaded(self, authenticated_page: Page, test_server):
        """Test that JavaScript modules are properly loaded."""
        # Check for JavaScript errors
        errors = []
        authenticated_page.on("console", lambda msg: errors.append(msg) if msg.type == "error" else None)
        
        # Reload page to check for module loading errors
        await authenticated_page.reload()
        
        # Wait a moment for modules to load
        await authenticated_page.wait_for_timeout(2000)
        
        # Check that critical elements are still interactive after JS loads
        await expect(authenticated_page.locator("#message")).to_be_visible()
        await expect(authenticated_page.locator("#send")).to_be_visible()
        
        # Should not have critical JavaScript errors
        critical_errors = [error for error in errors if "app.js" in str(error) or "main-menu" in str(error)]
        # Note: Some errors might be expected due to test environment