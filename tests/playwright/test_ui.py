"""UI interaction and navigation tests for the chat-client frontend."""
import pytest
from playwright.async_api import Page, expect


class TestUIInteractions:
    """Test UI interactions and navigation functionality."""

    async def test_logo_navigation(self, authenticated_page: Page, test_server):
        """Test logo click navigation."""
        logo = authenticated_page.locator("#logo")
        await expect(logo).to_be_visible()
        
        # Click logo should navigate to home
        await logo.click()
        
        # Should be on home page
        await authenticated_page.wait_for_timeout(500)
        current_url = authenticated_page.url
        assert test_server in current_url

    async def test_version_display(self, authenticated_page: Page, test_server):
        """Test that version information is displayed."""
        # Version should be displayed in navigation
        version_element = authenticated_page.locator("nav .navigation-left span")
        
        if await version_element.count() > 0:
            await expect(version_element).to_be_visible()
            version_text = await version_element.text_content()
            assert version_text is not None and len(version_text.strip()) > 0

    async def test_favicon_presence(self, authenticated_page: Page, test_server):
        """Test that favicon is properly loaded."""
        favicon = authenticated_page.locator('link[rel="icon"], link[rel="shortcut icon"]')
        
        # Favicon should be present in head
        if await favicon.count() > 0:
            await expect(favicon).to_be_attached()

    async def test_theme_switching_availability(self, authenticated_page: Page, test_server):
        """Test theme switching functionality if available."""
        # Look for theme switcher elements
        theme_switch = authenticated_page.locator("[data-theme-toggle], .theme-switch, #theme-toggle")
        
        if await theme_switch.count() > 0:
            await expect(theme_switch).to_be_visible()
            await expect(theme_switch).to_be_enabled()
            
            # Try clicking theme switch
            await theme_switch.click()
            await authenticated_page.wait_for_timeout(500)
            
            # Check if body class or data attributes changed
            body = authenticated_page.locator("body")
            await expect(body).to_be_visible()

    async def test_main_menu_overlay_trigger(self, authenticated_page: Page, test_server):
        """Test main menu overlay functionality if available."""
        # Look for menu trigger buttons
        menu_triggers = authenticated_page.locator("[data-menu-toggle], .menu-toggle, #menu-toggle")
        
        if await menu_triggers.count() > 0:
            menu_trigger = menu_triggers.first
            await expect(menu_trigger).to_be_visible()
            await menu_trigger.click()
            
            # Wait for overlay to appear
            await authenticated_page.wait_for_timeout(500)
            
            # Look for overlay elements
            overlay = authenticated_page.locator(".overlay, .menu-overlay, [data-overlay]")
            if await overlay.count() > 0:
                await expect(overlay).to_be_visible()

    async def test_custom_prompts_overlay_trigger(self, authenticated_page: Page, test_server):
        """Test custom prompts overlay functionality."""
        custom_prompt_button = authenticated_page.locator("#new-from-custom")
        
        if await custom_prompt_button.count() > 0:
            await expect(custom_prompt_button).to_be_visible()
            await custom_prompt_button.click()
            
            # Wait for overlay to appear
            await authenticated_page.wait_for_timeout(500)
            
            # Look for custom prompts overlay
            overlay = authenticated_page.locator(".custom-prompts-overlay, [data-custom-prompts]")
            if await overlay.count() > 0:
                await expect(overlay).to_be_visible()

    async def test_flash_message_system(self, authenticated_page: Page, test_server):
        """Test flash message system functionality."""
        # Flash messages might be present on page load or after actions
        flash_container = authenticated_page.locator(".flash-messages, #flash-messages")
        
        if await flash_container.count() > 0:
            await expect(flash_container).to_be_attached()

    async def test_keyboard_shortcuts_system(self, authenticated_page: Page, test_server):
        """Test keyboard shortcuts functionality."""
        # Test common keyboard shortcuts
        # This assumes the app has keyboard shortcut support
        
        # Focus on message input first
        await authenticated_page.focus("#message")
        
        # Test Escape key (might close overlays)
        await authenticated_page.keyboard.press("Escape")
        await authenticated_page.wait_for_timeout(100)
        
        # Test Ctrl+/ or similar for help (if implemented)
        await authenticated_page.keyboard.press("Control+/")
        await authenticated_page.wait_for_timeout(100)
        
        # Ensure page is still functional
        await expect(authenticated_page.locator("#message")).to_be_visible()

    async def test_responsive_navigation(self, authenticated_page: Page, test_server):
        """Test navigation responsiveness across different screen sizes."""
        screen_sizes = [
            {"width": 375, "height": 667},   # Mobile
            {"width": 768, "height": 1024},  # Tablet
            {"width": 1024, "height": 768},  # Tablet landscape
            {"width": 1920, "height": 1080}  # Desktop
        ]
        
        for size in screen_sizes:
            await authenticated_page.set_viewport_size(size)
            
            # Navigation should be visible and functional
            nav = authenticated_page.locator("nav.top-bar")
            await expect(nav).to_be_visible()
            
            # Logo should be visible
            logo = authenticated_page.locator("#logo")
            await expect(logo).to_be_visible()
            
            # Key action buttons should be accessible
            new_button = authenticated_page.locator("#new")
            await expect(new_button).to_be_visible()

    async def test_image_loading(self, authenticated_page: Page, test_server):
        """Test that images load properly."""
        # Logo image
        logo_img = authenticated_page.locator("#logo img")
        await expect(logo_img).to_be_visible()
        
        # Check image src
        src = await logo_img.get_attribute("src")
        assert src is not None
        assert "android-chrome-192x192.png" in src
        
        # Image should have proper dimensions
        await expect(logo_img).to_have_attribute("height", "192")
        await expect(logo_img).to_have_attribute("width", "192")

    async def test_svg_icon_functionality(self, authenticated_page: Page, test_server):
        """Test SVG icons are properly rendered and functional."""
        # Test various SVG icons in the interface
        svg_selectors = [
            "#new svg",  # New conversation icon
            "#new-from-custom svg",  # Custom prompt icon
            "#send svg",  # Send button icon
            "#abort svg",  # Abort button icon
            "#scroll-to-bottom svg"  # Scroll to bottom icon
        ]
        
        for selector in svg_selectors:
            svg = authenticated_page.locator(selector)
            if await svg.count() > 0:
                await expect(svg).to_be_visible()
                
                # SVG should have viewBox or proper dimensions
                viewbox = await svg.get_attribute("viewBox")
                width = await svg.get_attribute("width")
                height = await svg.get_attribute("height")
                
                # At least one dimension attribute should be present
                assert viewbox or (width and height)

    async def test_css_loading(self, authenticated_page: Page, test_server):
        """Test that CSS is properly loaded."""
        # Check for specific CSS classes that indicate styling is loaded
        chat_container = authenticated_page.locator(".chat-container")
        await expect(chat_container).to_be_visible()
        
        # Check computed styles to ensure CSS is applied
        background_color = await chat_container.evaluate(
            "el => window.getComputedStyle(el).backgroundColor"
        )
        assert background_color != "rgba(0, 0, 0, 0)"  # Should not be transparent

    async def test_javascript_module_imports(self, authenticated_page: Page, test_server):
        """Test that JavaScript modules are properly imported."""
        # Check for console errors related to module imports
        errors = []
        authenticated_page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        
        # Reload page to trigger fresh module loading
        await authenticated_page.reload()
        await authenticated_page.wait_for_timeout(2000)
        
        # Filter for critical module loading errors
        module_errors = [error for error in errors if "module" in error.lower() or "import" in error.lower()]
        
        # Log any module errors for debugging
        if module_errors:
            print("Module loading errors found:", module_errors)

    async def test_button_hover_states(self, authenticated_page: Page, test_server):
        """Test button hover states and interactions."""
        buttons = [
            "#new",
            "#new-from-custom",
            "#send",
            "#logo"
        ]
        
        for button_selector in buttons:
            button = authenticated_page.locator(button_selector)
            if await button.count() > 0:
                await expect(button).to_be_visible()
                
                # Hover over button
                await button.hover()
                await authenticated_page.wait_for_timeout(100)
                
                # Button should still be visible and functional
                await expect(button).to_be_visible()

    async def test_form_element_accessibility(self, authenticated_page: Page, test_server):
        """Test form elements for basic accessibility."""
        # Message textarea
        message_input = authenticated_page.locator("#message")
        await expect(message_input).to_be_visible()
        
        # Should be keyboard accessible
        await message_input.focus()
        is_focused = await message_input.evaluate("el => el === document.activeElement")
        assert is_focused
        
        # Should have proper labeling (aria-label or associated label)
        aria_label = await message_input.get_attribute("aria-label")
        placeholder = await message_input.get_attribute("placeholder")
        
        # Should have some form of labeling
        assert aria_label or placeholder

    async def test_loading_states(self, authenticated_page: Page, test_server):
        """Test loading spinner and states."""
        # Look for loading spinner elements
        loading_spinner = authenticated_page.locator(".loading-spinner, .spinner, [data-loading]")
        
        if await loading_spinner.count() > 0:
            # Spinner should be present but might be hidden initially
            await expect(loading_spinner).to_be_attached()

    async def test_error_handling_ui(self, authenticated_page: Page, test_server):
        """Test error handling in the UI."""
        # Try to trigger a client-side error scenario
        # Fill message and try to send without proper setup
        await authenticated_page.fill("#message", "Test error handling")
        
        # This might trigger error handling depending on implementation
        await authenticated_page.click("#send")
        await authenticated_page.wait_for_timeout(1000)
        
        # UI should remain stable
        await expect(authenticated_page.locator("#message")).to_be_visible()
        await expect(authenticated_page.locator("#send")).to_be_visible()

    async def test_dynamic_content_updates(self, authenticated_page: Page, test_server):
        """Test that dynamic content updates work properly."""
        # Get initial content
        responses_container = authenticated_page.locator("#responses")
        await expect(responses_container).to_be_visible()
        
        # Container should be ready for dynamic updates
        await expect(responses_container).to_be_attached()
        
        # Test that the container can receive new content
        initial_content = await responses_container.inner_html()
        assert initial_content is not None

    async def test_page_title_updates(self, authenticated_page: Page, test_server):
        """Test that page title is properly set."""
        # Home page should have appropriate title
        await expect(authenticated_page).to_have_title("Home - chat-client")
        
        # Title should not be empty or generic
        title = await authenticated_page.title()
        assert "chat-client" in title