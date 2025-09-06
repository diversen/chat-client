# Starlette Backend Test Suite

This directory contains comprehensive tests for the Starlette backend of the chat-client application. The tests validate all endpoints, authentication, error handling, and core functionality.

## Test Structure

```
tests/
├── README.md                     # This file
├── run_all_tests.py             # Main test runner
├── test_starlette_simple.py     # Basic functionality tests
├── test_starlette_comprehensive.py # Complete test suite
├── test_base.py                 # Test utilities and base classes (unused)
├── test_*_endpoints.py          # Individual endpoint test files (unused)
├── test_config.py              # Test configuration (unused)
└── test_*.py                   # Original test scripts
```

## Quick Start

### Prerequisites
1. Make sure the chat-client is installed: `pip install -e .`
2. Initialize the database: `chat-client init-system`

### Running Tests

**Run all tests:**
```bash
python tests/run_all_tests.py
```

**Run simple tests only:**
```bash
python tests/test_starlette_simple.py
```

**Run comprehensive tests only:**
```bash
python tests/test_starlette_comprehensive.py
```

## Test Categories

### 1. Simple Tests (`test_starlette_simple.py`)
Basic functionality tests that verify:
- ✅ Error endpoint functionality
- ✅ Protected route authentication
- ✅ Configuration endpoint
- ✅ Models list endpoint
- ✅ User routes (signup, login, captcha)
- ✅ Basic authenticated routes
- ✅ JSON endpoint authentication

### 2. Comprehensive Tests (`test_starlette_comprehensive.py`)
Full functionality tests covering:
- ✅ **Chat Endpoints**: Streaming, dialogs, messages, CRUD operations
- ✅ **User Endpoints**: Registration, authentication, profile management
- ✅ **Prompt Endpoints**: CRUD operations for user prompts
- ✅ **Error Endpoints**: Error logging functionality
- ✅ **Tool Endpoints**: Tool execution system
- ✅ **Validation**: Error handling and edge cases

## Test Coverage

The test suite covers all major Starlette routes and endpoints:

### Chat Endpoints (10 routes)
- `GET /` - Chat page
- `GET /chat/{dialog_id}` - Chat page with dialog
- `POST /chat` - Chat streaming
- `POST /tools/{tool}` - Tool execution
- `GET /config` - Frontend configuration
- `GET /list` - Available models
- `POST /chat/create-dialog` - Create dialog
- `POST /chat/create-message/{dialog_id}` - Create message
- `POST /chat/update-message/{message_id}` - Update message
- `POST /chat/delete-dialog/{dialog_id}` - Delete dialog
- `GET /chat/get-dialog/{dialog_id}` - Get dialog
- `GET /chat/get-messages/{dialog_id}` - Get messages

### User Endpoints (12 routes)
- `GET /captcha` - Captcha generation
- `GET/POST /user/signup` - User registration
- `GET/POST /user/login` - User authentication
- `GET/POST /user/verify` - Account verification
- `GET /user/logout` - User logout
- `GET/POST /user/reset` - Password reset
- `GET/POST /user/new-password` - New password setting
- `GET /user/dialogs` - List user dialogs
- `GET /user/dialogs/json` - List dialogs (JSON)
- `GET/POST /user/profile` - Profile management
- `GET /user/is-logged-in` - Authentication check

### Prompt Endpoints (8 routes)
- `GET /prompt` - List prompts
- `GET /prompt/json` - List prompts (JSON)
- `GET/POST /prompt/create` - Create prompt
- `GET /prompt/{prompt_id}` - Prompt detail
- `GET/POST /prompt/{prompt_id}/edit` - Edit prompt
- `POST /prompt/{prompt_id}/delete` - Delete prompt
- `GET /prompt/{prompt_id}/json` - Prompt detail (JSON)

### Error Endpoints (1 route)
- `POST /error/log` - Error logging

## Testing Approach

### Mocking Strategy
Tests use Python's `unittest.mock` to mock external dependencies:
- **Database Operations**: Mocked to avoid database setup/teardown
- **LLM API Calls**: Mocked to avoid external API dependencies
- **Email Services**: Mocked to avoid SMTP requirements
- **User Sessions**: Mocked for authentication testing

### TestClient Usage
All tests use Starlette's built-in `TestClient` which:
- Provides a test server environment
- Handles HTTP requests/responses
- Supports async operations
- Integrates with the application middleware stack

### Error Testing
Tests cover various error scenarios:
- Invalid authentication
- Validation errors
- Missing resources (404 errors)
- Server errors (500 errors)
- Edge cases and boundary conditions

## Configuration for Testing

The tests are designed to work with the default configuration but handle common issues:

### Database Initialization
- Tests expect the database to be initialized (`chat-client init-system`)
- The test runner will attempt to initialize if needed

### Model Configuration
- Tests work with or without ollama running
- Mock models are used for testing purposes
- No real API calls are made to LLM providers

### Dependencies
Tests require only the standard chat-client dependencies:
- `starlette` - Web framework
- `unittest.mock` - Mocking framework (built-in)
- Standard Python libraries

## Development Guidelines

### Adding New Tests

1. **For new endpoints**: Add test methods to `test_starlette_comprehensive.py`
2. **For new functionality**: Create focused test methods
3. **Follow patterns**: Use existing test structure and mocking patterns

### Test Structure
```python
def test_endpoint_name(self):
    """Test description"""
    with TestClient(self.app) as client:
        # Mock dependencies
        with patch('module.function', return_value=mock_data):
            # Make request
            response = client.get("/endpoint")
            
            # Assert results
            assert response.status_code == 200
            data = response.json()
            assert data["expected_field"] == expected_value
```

### Mocking Best Practices
- Mock at the repository/service level, not the database level
- Use specific return values rather than generic mocks
- Mock authentication consistently
- Handle both success and error cases

## Troubleshooting

### Common Issues

**"No such table" errors:**
```bash
# Initialize the database first
chat-client init-system
```

**"Connection refused" errors:**
- These are expected when ollama is not running
- Tests mock LLM calls, so this doesn't affect test results
- The configuration handles this gracefully

**Import errors:**
```bash
# Make sure chat-client is installed
pip install -e .

# Run from project root
cd /path/to/chat-client
python tests/run_all_tests.py
```

### Debug Mode
For verbose output, you can modify log levels in the test files or run with Python's verbose mode:
```bash
python -v tests/test_starlette_comprehensive.py
```

## Integration with CI/CD

The test suite is designed to work in CI/CD environments:
- No external dependencies (database is SQLite)
- Self-contained (creates test configuration)
- Proper exit codes (0 for success, 1 for failure)
- Clear output for debugging

### GitHub Actions Example
```yaml
- name: Run Backend Tests
  run: |
    pip install -e .
    python tests/run_all_tests.py
```

## Future Improvements

Potential enhancements to the test suite:
- [ ] Performance testing for streaming endpoints
- [ ] Load testing for concurrent users
- [ ] Database integration tests with real database
- [ ] End-to-end testing with real LLM APIs
- [ ] Security testing for authentication flows
- [ ] WebSocket testing if implemented

## Contributing

When adding new features to the backend:
1. Write tests first (TDD approach)
2. Ensure all existing tests pass
3. Add new tests to cover new functionality
4. Update documentation if needed
5. Run the full test suite before submitting PRs

## Support

If you encounter issues with the tests:
1. Check this README for common solutions
2. Verify your environment setup
3. Run individual test files to isolate issues
4. Check the project's GitHub issues for known problems