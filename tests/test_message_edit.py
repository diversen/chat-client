import json
import asyncio
from tests.test_base import BaseTestCase


class TestMessageEdit(BaseTestCase):

    def test_update_message_endpoint(self):
        """Test the update_message endpoint functionality"""

        async def async_test():
            # Create a user and login
            user_id = await self.create_test_user()

            # Create a dialog
            dialog_response = await self.client.post(
                "/chat/create-dialog", json={"title": "Test Dialog"}, cookies=self.session_cookies(user_id)
            )
            self.assertEqual(dialog_response.status_code, 200)
            dialog_data = dialog_response.json()
            dialog_id = dialog_data["dialog_id"]

            # Create a user message
            message_response = await self.client.post(
                f"/chat/create-message/{dialog_id}",
                json={"role": "user", "content": "Original message"},
                cookies=self.session_cookies(user_id),
            )
            self.assertEqual(message_response.status_code, 200)
            message_data = message_response.json()
            message_id = message_data["message_id"]

            # Create an assistant message after the user message
            assistant_response = await self.client.post(
                f"/chat/create-message/{dialog_id}",
                json={"role": "assistant", "content": "Assistant response"},
                cookies=self.session_cookies(user_id),
            )
            self.assertEqual(assistant_response.status_code, 200)

            # Update the user message
            update_response = await self.client.post(
                f"/chat/update-message/{message_id}", json={"content": "Updated message content"}, cookies=self.session_cookies(user_id)
            )
            self.assertEqual(update_response.status_code, 200)
            update_data = update_response.json()
            self.assertFalse(update_data.get("error", True))
            self.assertEqual(update_data["content"], "Updated message content")

            # Verify the message was updated
            messages_response = await self.client.get(f"/chat/get-messages/{dialog_id}", cookies=self.session_cookies(user_id))
            self.assertEqual(messages_response.status_code, 200)
            messages = messages_response.json()

            # Should only have the updated user message (assistant message should be deactivated)
            active_messages = [m for m in messages]
            self.assertEqual(len(active_messages), 1)
            self.assertEqual(active_messages[0]["content"], "Updated message content")
            self.assertEqual(active_messages[0]["role"], "user")

        asyncio.run(async_test())

    def test_update_message_validation(self):
        """Test update_message endpoint validation"""

        async def async_test():
            # Create a user and login
            user_id = await self.create_test_user()

            # Try to update non-existent message
            update_response = await self.client.post(
                "/chat/update-message/999999", json={"content": "Updated content"}, cookies=self.session_cookies(user_id)
            )
            self.assertEqual(update_response.status_code, 200)
            update_data = update_response.json()
            self.assertTrue(update_data.get("error", False))

            # Try to update with empty content
            # First create a valid message
            dialog_response = await self.client.post(
                "/chat/create-dialog", json={"title": "Test Dialog"}, cookies=self.session_cookies(user_id)
            )
            dialog_data = dialog_response.json()
            dialog_id = dialog_data["dialog_id"]

            message_response = await self.client.post(
                f"/chat/create-message/{dialog_id}",
                json={"role": "user", "content": "Original message"},
                cookies=self.session_cookies(user_id),
            )
            message_data = message_response.json()
            message_id = message_data["message_id"]

            # Try to update with empty content
            update_response = await self.client.post(
                f"/chat/update-message/{message_id}", json={"content": ""}, cookies=self.session_cookies(user_id)
            )
            self.assertEqual(update_response.status_code, 200)
            update_data = update_response.json()
            self.assertTrue(update_data.get("error", False))
            self.assertIn("empty", update_data.get("message", "").lower())

        asyncio.run(async_test())


if __name__ == "__main__":
    import unittest

    unittest.main()
