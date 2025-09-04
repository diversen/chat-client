# GitHub Copilot Instructions for chat-client

## Project Overview

This is a simple Python-based LLM chat client application that provides a web interface for chatting with various Large Language Models. The application supports multiple LLM providers through OpenAI-compatible APIs (ollama, OpenAI, etc.) and includes features like user authentication, chat history, tool support, and Python code execution.

## Architecture & Key Technologies

### Backend Stack
- **Framework**: Starlette (ASGI web framework)
- **Database**: SQLite with SQLAlchemy ORM and aiosqlite for async operations
- **Migrations**: Alembic for database schema management
- **Authentication**: Custom user authentication with bcrypt password hashing
- **LLM Integration**: OpenAI API compatible clients (supports ollama, OpenAI, etc.)
- **Python Version**: 3.10+

### Frontend Stack
- **Templates**: Jinja2 templating engine
- **Static Assets**: HTML/CSS/JavaScript with modern features
- **Markdown Rendering**: markdown-it with table support
- **Code Highlighting**: highlight.js with Atom One themes
- **Math Rendering**: MathJax support for mathematical expressions
- **UI Features**: Dark/light mode toggle, responsive design

### Development Tools
- **Package Management**: uv (modern Python package installer)
- **Code Formatting**: Black (line length: 140 characters)
- **Linting**: Flake8 with custom configuration
- **Type Checking**: MyPy
- **CLI**: Click for command-line interface
- **Testing**: Standard Python unittest/pytest

## Project Structure

```
chat_client/
├── __init__.py              # Package initialization and version
├── main.py                  # Starlette application setup
├── cli.py                   # Click-based CLI commands
├── models.py                # SQLAlchemy database models
├── core/                    # Core functionality
│   ├── exceptions.py        # Custom exceptions and handlers
│   ├── middleware.py        # Starlette middleware
│   ├── templates.py         # Template configuration
│   └── logging.py           # Logging setup
├── database/                # Database layer
│   ├── db_session.py        # Database session management
│   ├── migration.py         # Alembic migration runner
│   └── cache.py            # Caching utilities
├── endpoints/               # API endpoints
│   ├── chat_endpoints.py    # Chat-related routes
│   ├── user_endpoints.py    # User authentication routes
│   ├── error_endpoints.py   # Error handling routes
│   └── prompt_endpoints.py  # Prompt management routes
├── repositories/            # Data access layer
│   └── user_repository.py   # User-related database operations
├── static/                  # Frontend assets
│   ├── css/                 # Stylesheets
│   ├── js/                  # JavaScript modules
│   └── dist/               # Third-party libraries
├── templates/               # Jinja2 HTML templates
├── tools/                   # LLM tools and utilities
│   ├── python_exec.py       # Python code execution tool
│   └── tools_utils.py       # Tool utilities
└── migrations/              # Alembic database migrations
```

## Development Guidelines

### Code Style & Conventions

1. **Python Code Style**:
   - Use Black formatting with 140 character line length
   - Follow PEP 8 with Flake8 configuration
   - Use type hints where appropriate (MyPy checked)
   - Prefer async/await for database operations

2. **Naming Conventions**:
   - Snake_case for variables, functions, and modules
   - PascalCase for classes
   - Constants in UPPER_CASE
   - Database models use singular names (User, not Users)

3. **Import Organization**:
   - Standard library imports first
   - Third-party imports second
   - Local application imports last
   - Use relative imports for internal modules

### Database Patterns

1. **Models** (`models.py`):
   - Use SQLAlchemy declarative base
   - Include proper relationships and foreign keys
   - Add `__repr__` methods for debugging

2. **Sessions** (`database/db_session.py`):
   - Use async session management
   - Enable foreign key constraints for SQLite
   - Handle connection lifecycle properly

3. **Migrations** (`migrations/`):
   - Use Alembic for schema changes
   - Generate migrations with: `alembic revision --autogenerate -m "Description"`
   - Migrations run automatically on server start

### API Endpoints

1. **Structure**:
   - Group related endpoints in separate modules
   - Use Starlette's routing system
   - Return appropriate HTTP status codes
   - Handle exceptions gracefully

2. **Request Handling**:
   - Use Pydantic models for request validation when needed
   - Handle both JSON and form data
   - Implement proper error responses

3. **Authentication**:
   - Use session-based authentication
   - Implement password hashing with bcrypt
   - Handle user registration and login flows

### Frontend Development

1. **Templates**:
   - Use Jinja2 with proper template inheritance
   - Keep templates modular and reusable
   - Include proper error handling in templates

2. **Static Assets**:
   - Organize CSS and JavaScript logically
   - Use modern JavaScript features
   - Implement responsive design principles
   - Support dark/light theme switching

3. **Client-Server Communication**:
   - Use fetch API for AJAX requests
   - Implement proper error handling
   - Support streaming responses for chat

### LLM Integration

1. **Provider Support**:
   - Use OpenAI-compatible API format
   - Support multiple providers (ollama, OpenAI, etc.)
   - Handle streaming responses appropriately

2. **Tool Integration**:
   - Implement tools in the `tools/` directory
   - Follow the established pattern for tool registration
   - Handle tool execution safely (especially Python execution)

3. **Chat Features**:
   - Support markdown rendering with syntax highlighting
   - Handle mathematical expressions with MathJax
   - Implement conversation history management

## Getting Started for Development

### Quick Start (Complete Setup from Scratch)

1. **Clone and Setup Environment**:
   ```bash
   git clone https://github.com/diversen/chat-client.git
   cd chat-client
   
   # Install uv if not already installed
   pip install uv
   
   # Create virtual environment and install dependencies
   uv venv
   source .venv/bin/activate
   uv pip install -e .
   ```

2. **Initialize the System**:
   ```bash
   # This creates data/config.py with default configuration
   chat-client
   
   # Run database migrations
   chat-client init-system
   
   # Create a user account (interactive prompts for email/password)
   chat-client create-user
   ```

3. **Configure LLM Providers** (choose one option):
   
   **Option A: With Ollama (requires ollama running on localhost:11434)**:
   ```bash
   # Install and start ollama first, then the default config will work
   # The system will automatically detect available ollama models
   ```
   
   **Option B: Without Ollama (for testing/development)**:
   Edit `data/config.py` and comment out the ollama provider:
   ```python
   PROVIDERS = {
       # "ollama": {
       #     "base_url": "http://localhost:11434/v1",
       #     "api_key": "ollama",
       # },
   }
   
   MODELS = {
       "test-model": "test",  # For testing without real models
   }
   
   # Comment out the ollama model discovery section (lines 89-98)
   ```
   
   **Option C: With OpenAI or other providers**:
   Edit `data/config.py`:
   ```python
   PROVIDERS = {
       "openai": {
           "base_url": "https://api.openai.com/v1",
           "api_key": "your-api-key-here",
       },
   }
   
   MODELS = {
       "gpt-4o-mini": "openai",
   }
   ```

4. **Start Development Server**:
   ```bash
   chat-client server-dev
   # Server will be available at http://localhost:8000
   # Supports hot reloading for development
   ```

### Common Setup Issues and Solutions

1. **"Error getting ollama provided models: Connection error"**:
   - **Solution A**: Install and start ollama: `ollama serve` 
   - **Solution B**: Edit `data/config.py` to remove or comment out ollama provider
   - **Solution C**: Configure different providers (OpenAI, etc.)

2. **Virtual Environment Issues**:
   - Always activate the virtual environment: `source .venv/bin/activate`
   - If uv commands fail: `pip install uv` first
   - Check Python version: requires 3.10+

3. **Database Migration Errors**:
   - Ensure `data/` directory exists and is writable
   - Run `chat-client init-system` before starting server
   - Database file will be created at `data/database.db`

4. **Port Already in Use**:
   - Use different port: `chat-client server-dev --port 8080`
   - Check for existing processes: `lsof -i :8000`

### Development Workflow

1. **Code Style and Linting**:
   ```bash
   # Format code (140 character line length)
   black chat_client/
   
   # Check for issues
   flake8 chat_client/
   
   # Type checking
   mypy chat_client/
   ```

2. **Testing**:
   ```bash
   # Run individual test files
   python tests/test_password_methods.py
   
   # Test specific functionality
   python tests/test_tools.py
   ```

3. **Database Changes**:
   ```bash
   # After modifying models.py, generate migration
   alembic revision --autogenerate -m "Description of changes"
   
   # Apply migrations
   chat-client init-system
   ```

4. **Server Options**:
   ```bash
   # Development server with custom settings
   chat-client server-dev --port 8080 --host 0.0.0.0
   
   # Production server (Linux/Mac only)
   chat-client server-prod --workers 3
   ```

### Configuration Deep Dive

1. **Key Configuration Files**:
   - `data/config.py` - Main configuration (created automatically)
   - `data/database.db` - SQLite database
   - `data/main.log` - Application logs

2. **Essential Configuration Options**:
   ```python
   # In data/config.py:
   LOG_LEVEL = logging.DEBUG        # For development
   SESSION_HTTPS_ONLY = False       # For local development
   RELOAD = True                    # Enable hot reloading
   
   # For development without HTTPS
   SESSION_SECRET_KEY = "your-secret-key"
   ```

3. **Environment Variables** (alternative to editing config.py):
   ```bash
   export OPENAI_API_KEY="your-key"
   export CHAT_CLIENT_LOG_LEVEL="DEBUG"
   ```

### Debugging and Development Tips

1. **Log Files**: Check `data/main.log` for detailed application logs
2. **Database Inspection**: Use SQLite browser or CLI to inspect `data/database.db`
3. **Hot Reloading**: Development server automatically reloads on file changes
4. **Network Testing**: Server binds to `0.0.0.0` by default, accessible from network
5. **Session Management**: Sessions are stored in database, clear with user logout

### Testing the System

1. **Web Interface Testing**:
   - Navigate to http://localhost:8000 in browser
   - Login with created user credentials
   - Test chat functionality (if models configured)

2. **API Testing**:
   ```bash
   # Test login endpoint
   curl -X POST http://localhost:8000/auth/login \
        -d "email=test@example.com&password=testpassword"
   
   # Test health check
   curl http://localhost:8000/health
   ```

## Common Development Tasks

### Adding New Features

1. **New Endpoint**:
   - Add route to appropriate endpoint module
   - Update main.py to include new routes
   - Add templates if needed
   - Test with manual verification

2. **Database Changes**:
   - Modify models.py
   - Generate migration: `alembic revision --autogenerate -m "Description"`
   - Test migration locally

3. **New LLM Tool**:
   - Create tool module in `tools/` directory
   - Register tool in the tool system
   - Add appropriate safety checks
   - Update documentation

### Testing Approach

1. **Unit Tests**:
   - Located in `tests/` directory
   - Test core functionality and utilities
   - Mock external dependencies (LLM APIs)

2. **Manual Testing**:
   - Use CLI commands for setup: `chat-client init-system`
   - Test with local development server: `chat-client server-dev`
   - Verify chat functionality with test models

### Configuration Management

1. **Config Files**:
   - Configuration stored in `data/config.py`
   - Use environment variables for sensitive data
   - Provide sensible defaults for development

2. **Development Setup**:
   - Use `uv` for dependency management
   - Support both pipx and local development installations
   - Document configuration requirements

## Specific Implementation Patterns

### Async Database Operations
```python
async def get_user(user_id: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
```

### Starlette Route Definition
```python
routes = [
    Route("/endpoint", endpoint_function, methods=["GET", "POST"]),
]
```

### Template Rendering
```python
def render_template(request, template_name, context={}):
    templates = Jinja2Templates(directory="templates")
    return templates.TemplateResponse(template_name, {"request": request, **context})
```

### Error Handling
```python
try:
    # operation
except SpecificException as e:
    logger.error(f"Error description: {e}")
    raise HTTPException(status_code=400, detail="User-friendly message")
```

## Performance Considerations

1. **Database**: Use connection pooling and proper indexing
2. **Static Files**: Serve static assets efficiently
3. **Streaming**: Implement proper streaming for long responses
4. **Caching**: Use appropriate caching strategies for frequently accessed data

## Security Considerations

1. **Authentication**: Proper password hashing and session management
2. **Input Validation**: Validate all user inputs
3. **Python Execution**: Sandbox Python code execution when enabled
4. **Dependencies**: Keep dependencies updated for security patches

## Deployment & Operations

1. **Production**: Use gunicorn or uvicorn for production deployment
2. **Monitoring**: Implement proper logging and error tracking
3. **Migrations**: Handle database migrations in production deployments
4. **Configuration**: Use environment-specific configuration files

## Development Environment Setup (Step-by-Step)

### First Time Setup Checklist
- [ ] Clone repository
- [ ] Install uv package manager (`pip install uv`)
- [ ] Create virtual environment (`uv venv`)
- [ ] Activate virtual environment (`source .venv/bin/activate`)
- [ ] Install in development mode (`uv pip install -e .`)
- [ ] Run initial setup (`chat-client` - this creates config.py)
- [ ] Configure LLM providers (edit `data/config.py`)
- [ ] Initialize database (`chat-client init-system`)
- [ ] Create user account (`chat-client create-user`)
- [ ] Start development server (`chat-client server-dev`)
- [ ] Test web interface (http://localhost:8000)

### Dependencies and Tools
- **Python**: 3.10+ required
- **Package Manager**: uv (preferred) or pip
- **Database**: SQLite (no external setup needed)
- **Server**: Uvicorn (development) / Gunicorn (production)
- **Code Quality**: Black (formatting), Flake8 (linting), MyPy (type checking)

### IDE Setup Recommendations
- Configure Black formatter with 140 character line length
- Enable Flake8 linting with project's .flake8 config
- Set up MyPy type checking (excludes tests, docs, migrations)
- Use Python 3.10+ interpreter from virtual environment

This project aims to provide a simple, extensible chat interface for LLMs while maintaining clean, maintainable code that follows Python best practices.