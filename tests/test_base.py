"""
Base test utilities for Starlette backend tests.
Provides TestClient setup, database fixtures, and common test utilities.
"""
import asyncio
import tempfile
import os
from pathlib import Path
from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event

# Import our models
from chat_client.models import Base


class TestDatabase:
    """Test database setup and teardown"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.engine = None
        self.session_factory = None

    async def setup(self):
        """Setup test database"""
        # Create async engine for testing with SQLite
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.db_path}",
            echo=False,
        )
        
        # Enable foreign key support for SQLite
        @event.listens_for(self.engine.sync_engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Create all tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def teardown(self):
        """Teardown test database"""
        if self.engine:
            await self.engine.dispose()
        
        # Clean up temporary files
        if self.db_path.exists():
            self.db_path.unlink()
        if Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir)

    async def get_session(self):
        """Get a test database session"""
        async with self.session_factory() as session:
            yield session


class BaseTestCase:
    """Base test case with common setup"""
    
    def __init__(self):
        self.client = None
        self.db = None

    def setup_method(self):
        """Setup before each test method"""
        # Create test client with mocked dependencies
        with patch('chat_client.endpoints.chat_endpoints.config') as mock_config:
            with patch('chat_client.endpoints.user_endpoints.config') as mock_user_config:
                with patch('chat_client.endpoints.prompt_endpoints.config') as mock_prompt_config:
                    # Mock configuration
                    mock_config.DEFAULT_MODEL = "test-model"
                    mock_config.PROVIDERS = {"test-provider": {"base_url": "http://test", "api_key": "test"}}
                    mock_config.MODELS = {"test-model": "test-provider"}
                    mock_config.TOOL_MODELS = []
                    mock_config.TOOL_REGISTRY = {}
                    mock_config.TOOLS = []
                    mock_config.TOOLS_CALLBACK = {}
                    mock_config.USE_KATEX = False
                    
                    # Import app after mocking config
                    from chat_client.main import app
                    self.client = TestClient(app)

    def teardown_method(self):
        """Teardown after each test method"""
        if self.client:
            self.client.__exit__(None, None, None)

    def create_test_user_data(self):
        """Create test user data for registration"""
        return {
            "email": "test@example.com",
            "password": "testpassword123",
            "password_repeat": "testpassword123",
            "captcha": "TEST"  # Mock captcha
        }


def run_async_test(coro):
    """Helper to run async functions in tests"""
    return asyncio.run(coro)


# Common test utilities
def mock_llm_response():
    """Mock LLM API response for testing"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].delta = MagicMock()
    mock_response.choices[0].delta.content = "Test response"
    mock_response.choices[0].delta.tool_calls = None
    mock_response.choices[0].finish_reason = "stop"
    mock_response.model_dump.return_value = {
        "choices": [{"delta": {"content": "Test response"}}]
    }
    return [mock_response]


def mock_openai_client():
    """Mock OpenAI client for testing"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_llm_response()
    return mock_client