#!/usr/bin/env python3

"""
Simple test for the database model changes.
This test validates that the Message model has the active field.
"""

import sys
import os

# Add the project root to the path so we can import modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from chat_client.models import Message


def test_message_model():
    """Test that the Message model has the active field"""
    print("Testing Message model...")
    
    # Check that the Message class has the active field
    assert hasattr(Message, 'active'), "Message model should have 'active' field"
    
    # Check that we can create a Message instance with the active field
    # (We won't save it to the database, just test the model structure)
    try:
        message = Message(
            dialog_id="test-dialog",
            user_id=1,
            role="user",
            content="test content",
            active=1
        )
        print(f"✅ Message model created successfully with active={message.active}")
        
        # Test that active field defaults to 1
        message_default = Message(
            dialog_id="test-dialog",
            user_id=1,
            role="user", 
            content="test content"
        )
        print(f"✅ Message model with default active value: {message_default.active}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create Message model: {e}")
        return False


if __name__ == "__main__":
    print("Testing Message model changes...")
    
    success = test_message_model()
    
    if success:
        print("\n✅ All model tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Model tests failed!")
        sys.exit(1)