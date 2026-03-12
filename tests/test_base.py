"""
Base test utilities for Starlette backend tests.
Provides shared helpers and pytest-compatible setup for endpoint suites.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from chat_client.models import Base


class TestDatabase:
    """Test database setup and teardown"""

    __test__ = False

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
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

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

    @pytest.fixture(autouse=True)
    def _setup_client(self, client):
        self.client = client

    def create_test_user_data(self):
        """Create test user data for registration"""
        return {
            "email": "test@example.com",
            "password": "testpassword123",
            "password_repeat": "testpassword123",
            "captcha": "TEST",  # Mock captcha
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
    mock_response.model_dump.return_value = {"choices": [{"delta": {"content": "Test response"}}]}
    return [mock_response]


def mock_openai_client():
    """Mock OpenAI client for testing"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_llm_response()
    return mock_client
