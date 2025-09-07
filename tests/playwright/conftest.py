"""Pytest configuration and fixtures for Playwright tests."""
import pytest
import asyncio
import os
import tempfile
import shutil
from pathlib import Path
import sqlite3
from contextlib import asynccontextmanager

# Ensure the chat_client module can be imported
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from chat_client.main import app
from chat_client.database.db_session import engine
from chat_client import cli
import data.config as config


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary data directory for tests."""
    temp_dir = tempfile.mkdtemp(prefix="chat_client_test_")
    
    # Create the data structure
    data_dir = Path(temp_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy config template and modify it for tests
    config_dist = project_root / "chat_client" / "config-dist.py"
    test_config = data_dir / "config.py"
    
    with open(config_dist, 'r') as f:
        config_content = f.read()
    
    # Modify config for test environment
    test_config_content = config_content.replace(
        'DATABASE_URL = "sqlite+aiosqlite:///data/database.db"',
        f'DATABASE_URL = "sqlite+aiosqlite:///{data_dir}/test_database.db"'
    ).replace(
        'LOG_FILE = "data/main.log"',
        f'LOG_FILE = "{data_dir}/test.log"'
    ).replace(
        'SESSION_HTTPS_ONLY = True',
        'SESSION_HTTPS_ONLY = False'
    ).replace(
        'RELOAD = False',
        'RELOAD = False'
    )
    
    # Add test model configuration
    test_config_content += """

# Test configuration additions
MODELS = {
    "test-model": "test",
}

PROVIDERS = {}  # No real providers for tests
"""
    
    with open(test_config, 'w') as f:
        f.write(test_config_content)
    
    # Set up environment
    old_cwd = os.getcwd()
    os.chdir(temp_dir)
    
    yield temp_dir
    
    # Cleanup
    os.chdir(old_cwd)
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="session")
async def setup_test_database(test_data_dir):
    """Initialize the test database."""
    # Change to test directory
    old_cwd = os.getcwd()
    os.chdir(test_data_dir)
    
    try:
        # Initialize database
        await cli.init_system()
        
        # Create a test user
        from chat_client.repositories import user_repository
        from unittest.mock import AsyncMock, patch
        
        # Mock the request object for user creation
        class MockRequest:
            def __init__(self):
                self._form_data = {
                    'email': 'test@example.com',
                    'password': 'test123456',
                    'password2': 'test123456'
                }
            
            async def form(self):
                return self._form_data
        
        request = MockRequest()
        
        # Create test user directly in database
        db_path = f"{test_data_dir}/data/test_database.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Hash the password
        import bcrypt
        password_hash = bcrypt.hashpw('test123456'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("""
            INSERT INTO users (email, password, verified, created_on) 
            VALUES (?, ?, 1, datetime('now'))
        """, ('test@example.com', password_hash))
        
        conn.commit()
        conn.close()
        
        yield db_path
        
    finally:
        os.chdir(old_cwd)


@pytest.fixture
async def test_server(setup_test_database, test_data_dir):
    """Start the test server."""
    import uvicorn
    import threading
    import time
    
    # Change to test directory
    old_cwd = os.getcwd()
    os.chdir(test_data_dir)
    
    # Start server in a separate thread
    server_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8001,  # Different port for tests
        log_level="error"  # Reduce noise
    )
    server = uvicorn.Server(server_config)
    
    def run_server():
        asyncio.run(server.serve())
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(2)
    
    yield "http://127.0.0.1:8001"
    
    # Cleanup
    os.chdir(old_cwd)


@pytest.fixture
def browser_context_args(browser_context_args):
    """Configure browser context for tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture
async def authenticated_page(page, test_server):
    """Create a page with an authenticated user session."""
    await page.goto(f"{test_server}/user/login")
    
    # Fill in login form
    await page.fill("#email", "test@example.com")
    await page.fill("#password", "test123456") 
    await page.click("#login")
    
    # Wait for redirect to home page
    await page.wait_for_url(f"{test_server}/")
    
    return page