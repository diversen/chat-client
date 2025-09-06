#!/usr/bin/env python3

"""
Test script for the update message functionality.
This test validates that:
1. Messages can be updated 
2. Newer messages in the same dialog are deactivated
3. Only active messages are returned by get_messages
"""

import asyncio
import sys
import os

# Add the project root to the path so we can import modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from chat_client.models import Dialog, Message, User
from chat_client.database.db_session import async_session
from chat_client.repositories.chat_repository import create_message, update_message, get_messages
from sqlalchemy import select
import uuid
import json
from datetime import datetime
from unittest.mock import AsyncMock


class MockRequest:
    def __init__(self, path_params=None, json_data=None):
        self.path_params = path_params or {}
        self._json_data = json_data or {}
    
    async def json(self):
        return self._json_data


async def setup_test_data():
    """Create test user, dialog and messages for testing"""
    async with async_session() as session:
        # Create a test user
        test_user = User(
            email="test@example.com",
            password_hash="test_hash",
            random="test_random"
        )
        session.add(test_user)
        await session.flush()
        user_id = test_user.user_id
        
        # Create a test dialog
        dialog_id = str(uuid.uuid4())
        test_dialog = Dialog(
            dialog_id=dialog_id,
            user_id=user_id,
            title="Test Dialog"
        )
        session.add(test_dialog)
        await session.flush()
        
        # Create test messages (we'll add them directly to control timing)
        messages = [
            Message(dialog_id=dialog_id, user_id=user_id, role="user", content="Message 1", active=1),
            Message(dialog_id=dialog_id, user_id=user_id, role="assistant", content="Response 1", active=1),
            Message(dialog_id=dialog_id, user_id=user_id, role="user", content="Message 2", active=1),
            Message(dialog_id=dialog_id, user_id=user_id, role="assistant", content="Response 2", active=1),
        ]
        
        for msg in messages:
            session.add(msg)
        
        await session.commit()
        
        # Get the message IDs for testing
        stmt = select(Message).where(Message.dialog_id == dialog_id).order_by(Message.created.asc())
        result = await session.execute(stmt)
        created_messages = result.scalars().all()
        
        return user_id, dialog_id, [msg.message_id for msg in created_messages]


async def test_update_message():
    """Test the update message functionality"""
    print("Setting up test data...")
    user_id, dialog_id, message_ids = await setup_test_data()
    
    print(f"Created user_id: {user_id}, dialog_id: {dialog_id}")
    print(f"Created message_ids: {message_ids}")
    
    # Test 1: Update the second message (index 1)
    print("\nTest 1: Updating second message...")
    
    mock_request = MockRequest(
        path_params={"message_id": str(message_ids[1])},
        json_data={"content": "Updated Response 1"}
    )
    
    result = await update_message(user_id, mock_request)
    print(f"Update result: {result}")
    
    # Test 2: Check that newer messages (indices 2, 3) are deactivated
    print("\nTest 2: Checking message states...")
    
    async with async_session() as session:
        stmt = select(Message).where(Message.dialog_id == dialog_id).order_by(Message.created.asc())
        result = await session.execute(stmt)
        messages = result.scalars().all()
        
        print("Message states after update:")
        for i, msg in enumerate(messages):
            print(f"  Message {i+1}: active={msg.active}, content='{msg.content[:20]}...'")
        
        # Verify the expected states
        assert messages[0].active == 1, "First message should remain active"
        assert messages[1].active == 1, "Updated message should remain active"
        assert messages[2].active == 0, "Third message should be deactivated"
        assert messages[3].active == 0, "Fourth message should be deactivated"
        assert messages[1].content == "Updated Response 1", "Content should be updated"
    
    # Test 3: Verify get_messages only returns active messages
    print("\nTest 3: Checking get_messages returns only active messages...")
    
    mock_request = MockRequest(path_params={"dialog_id": dialog_id})
    active_messages = await get_messages(user_id, mock_request)
    
    print(f"Active messages count: {len(active_messages)}")
    print("Active messages:")
    for msg in active_messages:
        print(f"  - {msg['role']}: {msg['content'][:30]}...")
    
    assert len(active_messages) == 2, "Should only return 2 active messages"
    assert active_messages[1]["content"] == "Updated Response 1", "Should return updated content"
    
    print("\n✅ All tests passed!")


async def cleanup_test_data():
    """Clean up test data"""
    async with async_session() as session:
        # Delete test messages and dialogs
        await session.execute("DELETE FROM message WHERE dialog_id LIKE 'test-%' OR user_id IN (SELECT user_id FROM users WHERE email = 'test@example.com')")
        await session.execute("DELETE FROM dialog WHERE user_id IN (SELECT user_id FROM users WHERE email = 'test@example.com')")
        await session.execute("DELETE FROM users WHERE email = 'test@example.com'")
        await session.commit()


if __name__ == "__main__":
    print("Testing update message functionality...")
    
    try:
        asyncio.run(test_update_message())
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up
        print("\nCleaning up test data...")
        try:
            asyncio.run(cleanup_test_data())
            print("✅ Cleanup completed")
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}")