"""Pytest configuration and fixtures for Playwright tests."""
import pytest
import asyncio
import os
import tempfile
import shutil
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure the chat_client module can be imported
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from chat_client.main import app
from chat_client.database.db_session import engine, async_session
from chat_client import cli
from chat_client.models import Base
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
    
    # Copy the existing config and modify for testing
    source_config = project_root / "data" / "config.py"
    test_config = data_dir / "config.py"
    
    # Read existing config
    with open(source_config, 'r') as f:
        config_content = f.read()
    
    # Modify for test environment - just change the database path and make it test-friendly
    test_config_content = config_content.replace(
        'DATABASE = Path(DATA_DIR) / Path("database.db")',
        'DATABASE = Path(DATA_DIR) / Path("database.db")'  # Keep the same, CLI will handle it
    ).replace(
        'SESSION_HTTPS_ONLY = False  # Set to False for testing',
        'SESSION_HTTPS_ONLY = False  # Set to False for testing'
    )
    
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
    # Change to test directory where our config is
    old_cwd = os.getcwd()
    os.chdir(test_data_dir)
    
    try:
        # The issue is that we need to force reload the config and database modules
        # Let's run the initialization in the test directory
        
        # Initialize database using the CLI function which will use the test config
        cli._before_server_start()
        
        # Now create test user using the same database path that the CLI just set up
        from chat_client.repositories.user_repository import _password_hash
        from chat_client.models import User
        import secrets
        import sqlite3
        
        # Get the actual database path that was just created
        test_db_path = f"{test_data_dir}/data/database.db"  # This is what CLI creates
        
        # Create user directly in the database using sqlite3 since the async session 
        # was created with the old config
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        # Hash the password using the same method as the app
        password_hash = _password_hash('test123456')
        
        cursor.execute("""
            INSERT INTO users (email, password_hash, random, verified, locked, created) 
            VALUES (?, ?, ?, 1, 0, datetime('now'))
        """, ('test@example.com', password_hash, secrets.token_urlsafe(32)))
        
        conn.commit()
        conn.close()
        
        yield test_db_path
        
    finally:
        os.chdir(old_cwd)


@pytest.fixture
def test_server(setup_test_database, test_data_dir):
    """Start the test server."""
    import uvicorn
    import threading
    import time
    import asyncio
    
    # Change to test directory
    old_cwd = os.getcwd()
    os.chdir(test_data_dir)
    
    # Start server in a separate thread with a new event loop
    server_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8001,  # Different port for tests
        log_level="error"  # Reduce noise
    )
    server = uvicorn.Server(server_config)
    
    def run_server():
        # Create new event loop for the server thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(3)  # Give it a bit more time
    
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