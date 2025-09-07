# Playwright Tests for Chat-Client

This directory contains comprehensive end-to-end tests for the chat-client frontend using Playwright.

## Overview

The Playwright tests ensure the frontend functionality works correctly by testing real user interactions with the web interface. These tests complement the existing backend API tests by validating the complete user experience.

## Test Coverage

### Authentication Tests (`test_auth.py`)
- User login and logout functionality
- Form validation and error handling  
- Password reset workflows
- Session management
- Redirect behavior for authenticated/unauthenticated users

### Chat Interface Tests (`test_chat.py`) 
- Chat page loading and layout
- Message input and send functionality
- Model selection dropdown
- UI controls (scroll, abort, new conversation)
- Responsive design across screen sizes
- JavaScript module loading

### UI Interaction Tests (`test_ui.py`)
- Navigation and menu interactions
- Theme switching (if available)
- Keyboard shortcuts and accessibility
- Image and icon loading
- Error handling and loading states
- Dynamic content updates

## Test Structure

```
tests/playwright/
├── README.md                 # This documentation
├── conftest.py              # Pytest fixtures and configuration
├── pytest.ini              # Pytest settings
├── playwright.config.py    # Playwright configuration 
├── run_tests.py            # Test runner script
├── validate_setup.py       # Setup validation script
├── test_auth.py            # Authentication tests
├── test_chat.py            # Chat interface tests  
├── test_ui.py              # UI interaction tests
└── utils/
    ├── __init__.py
    └── helpers.py          # Test utilities and helpers
```

## Setup and Installation

### 1. Install Dependencies

```bash
# Install test dependencies
pip install -e ".[test]"

# Or install individually
pip install playwright pytest pytest-playwright pytest-asyncio
```

### 2. Install Browser Binaries

```bash
# Install Chromium (recommended for CI)
python -m playwright install chromium

# Or install all browsers
python -m playwright install
```

### 3. Validate Setup

```bash
# Run setup validation
python tests/playwright/validate_setup.py
```

## Running Tests

### Using the Test Runner (Recommended)

```bash
# Run all tests with browser installation
python tests/playwright/run_tests.py --install-browsers

# Run tests in headed mode (show browser)
python tests/playwright/run_tests.py --headed

# Run specific test file
python tests/playwright/run_tests.py --test test_auth.py

# Run with verbose output
python tests/playwright/run_tests.py --verbose
```

### Using Pytest Directly

```bash
# Run all playwright tests
pytest tests/playwright/

# Run specific test file
pytest tests/playwright/test_auth.py

# Run with headed browser (for debugging)
pytest tests/playwright/ --headed

# Run with specific browser
pytest tests/playwright/ --browser=chromium

# Run with verbose output
pytest tests/playwright/ -v
```

### Test Markers

Tests can be filtered using pytest markers:

```bash
# Run only authentication tests
pytest tests/playwright/ -m auth

# Run only UI tests  
pytest tests/playwright/ -m ui

# Run only chat functionality tests
pytest tests/playwright/ -m chat

# Skip slow tests
pytest tests/playwright/ -m "not slow"
```

## Test Configuration

### Environment Setup

The tests use a temporary database and test server configuration:

- **Database**: Temporary SQLite database created for each test session
- **Server**: Test server running on port 8001
- **User**: Pre-created test user (test@example.com / test123456)
- **Models**: Mock models for testing without external LLM providers

### Browser Configuration

- **Default Browser**: Chromium (fastest, best for CI)
- **Viewport**: 1280x720 (can be overridden per test)
- **Screenshots**: Taken on test failures
- **Videos**: Recorded for failed tests (in videos/ directory)

### Fixtures

Key test fixtures available:

- `test_server`: Starts test server with temporary database
- `authenticated_page`: Browser page with logged-in user session
- `test_data_dir`: Temporary directory with test configuration
- `setup_test_database`: Initializes test database with test user

## Development Guidelines

### Writing New Tests

1. **Use the existing fixtures** for common setup (authentication, server, etc.)
2. **Follow naming conventions**: `test_*.py` files, `test_*` functions
3. **Use proper assertions**: Prefer Playwright's `expect()` for web elements
4. **Add appropriate markers**: `@pytest.mark.auth`, `@pytest.mark.ui`, etc.
5. **Handle timeouts**: Use appropriate waits for dynamic content

### Test Best Practices

1. **Independent Tests**: Each test should be self-contained
2. **Cleanup**: Tests should not leave artifacts or affect other tests
3. **Realistic Scenarios**: Test real user workflows, not just API calls
4. **Error Handling**: Test both success and failure scenarios
5. **Accessibility**: Include basic accessibility checks where relevant

### Example Test

```python
async def test_new_feature(authenticated_page: Page, test_server):
    """Test description of what this validates."""
    # Navigate to the feature
    await authenticated_page.goto(f"{test_server}/feature")
    
    # Interact with the UI
    await authenticated_page.click("#feature-button")
    
    # Verify expected behavior
    await expect(authenticated_page.locator("#result")).to_be_visible()
    await expect(authenticated_page.locator("#result")).to_contain_text("Expected output")
```

## Debugging Tests

### Running Tests in Headed Mode

```bash
# See the browser during test execution
pytest tests/playwright/ --headed

# Run with slower execution for debugging
pytest tests/playwright/ --headed --slowmo 1000
```

### Screenshots and Videos

- **Screenshots**: Automatically taken on test failures
- **Videos**: Recorded for failed tests (enable with `--video=on`)
- **Location**: `tests/playwright/test-results/`

### Debugging Tools

```bash
# Run tests with playwright debugging tools
PWDEBUG=1 pytest tests/playwright/test_auth.py::test_login_page_loads

# Run with console output
pytest tests/playwright/ -s --log-cli-level=DEBUG
```

## Continuous Integration

### GitHub Actions Example

```yaml
- name: Install dependencies
  run: |
    pip install -e ".[test]"
    python -m playwright install chromium

- name: Run Playwright tests
  run: |
    pytest tests/playwright/ --browser=chromium
```

### Docker Support

The tests can run in Docker environments with proper display configuration:

```dockerfile
RUN python -m playwright install-deps chromium
RUN python -m playwright install chromium
```

## Troubleshooting

### Common Issues

1. **Browser Installation Fails**
   ```bash
   # Try installing dependencies first
   python -m playwright install-deps
   python -m playwright install chromium
   ```

2. **Tests Timeout**
   - Increase timeout values in test configuration
   - Check if test server is starting properly
   - Verify network connectivity

3. **Database Errors**
   - Ensure test has write permissions to create temp files
   - Check that SQLite is properly installed
   - Verify test isolation (no concurrent access)

4. **JavaScript Errors**
   - Check browser console output in headed mode
   - Verify static files are served correctly
   - Test with different browsers

### Getting Help

- Check the test output for specific error messages
- Use `--headed` mode to see what's happening visually
- Add debugging prints or breakpoints in test code
- Review the test logs and screenshots on failure

## Contributing

When adding new Playwright tests:

1. Follow the existing patterns and structure
2. Add appropriate documentation and comments
3. Test on multiple screen sizes when relevant
4. Include both positive and negative test cases
5. Update this README if adding new test categories