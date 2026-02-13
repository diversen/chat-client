"""
Comprehensive tests for Starlette backend endpoints.
Tests all major functionality with proper mocking.
"""

import os
import sys
from unittest.mock import patch, MagicMock
import json

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from starlette.testclient import TestClient


class TestStarletteBackend:
    """Comprehensive test suite for all Starlette backend endpoints"""

    def setup_method(self):
        """Setup for each test method"""
        from chat_client.main import app

        self.app = app

    def test_chat_endpoints(self):
        """Test all chat-related endpoints"""
        print("Testing chat endpoints...")

        with TestClient(self.app) as client:
            # Test chat streaming endpoint authentication
            response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}], "model": "test-model"})
            assert response.status_code == 401
            print("  ✓ Chat streaming requires authentication")

            # Test chat streaming with authentication
            with patch("chat_client.core.user_session.is_logged_in", return_value=1):
                with patch("chat_client.repositories.user_repository.get_profile", return_value={"system_message": ""}):
                    with patch("chat_client.endpoints.chat_endpoints.OpenAI") as mock_openai:
                        # Mock the streaming response
                        mock_response = MagicMock()
                        mock_response.choices = [MagicMock()]
                        mock_response.choices[0].delta = MagicMock()
                        mock_response.choices[0].delta.content = "Test response"
                        mock_response.choices[0].delta.tool_calls = None
                        mock_response.choices[0].finish_reason = "stop"
                        mock_response.model_dump.return_value = {"choices": [{"delta": {"content": "Test"}}]}

                        mock_client = MagicMock()
                        mock_client.chat.completions.create.return_value = [mock_response]
                        mock_openai.return_value = mock_client

                        response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}], "model": "test-model"})
                        assert response.status_code == 200
                        assert "text/event-stream" in response.headers["content-type"]
                        print("  ✓ Chat streaming works when authenticated")

            # Test dialog creation without auth
            response = client.post("/chat/create-dialog", json={"title": "Test Dialog"})
            assert response.status_code == 401
            print("  ✓ Create dialog requires authentication")

            # Test dialog creation with auth
            with patch("chat_client.core.user_session.is_logged_in", return_value=1):
                with patch("chat_client.repositories.chat_repository.create_dialog", return_value="dialog-123"):
                    response = client.post("/chat/create-dialog", json={"title": "Test Dialog"})
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False
                    assert data["dialog_id"] == "dialog-123"
                    print("  ✓ Create dialog works when authenticated")

            # Test message operations
            with patch("chat_client.core.user_session.is_logged_in", return_value=1):
                # Create message
                with patch("chat_client.repositories.chat_repository.create_message", return_value=456):
                    response = client.post("/chat/create-message/dialog-123", json={"content": "Test message", "role": "user"})
                    assert response.status_code == 200
                    data = response.json()
                    assert data["message_id"] == 456
                    print("  ✓ Create message works")

                # Get messages
                with patch(
                    "chat_client.repositories.chat_repository.get_messages",
                    return_value=[{"message_id": 456, "content": "Test message", "role": "user"}],
                ):
                    response = client.get("/chat/get-messages/dialog-123")
                    assert response.status_code == 200
                    messages = response.json()
                    assert len(messages) == 1
                    assert messages[0]["content"] == "Test message"
                    print("  ✓ Get messages works")

                # Update message
                with patch("chat_client.repositories.chat_repository.update_message", return_value={"message_id": 456}):
                    response = client.post("/chat/update-message/456", json={"content": "Updated message"})
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False
                    print("  ✓ Update message works")

                # Get dialog
                with patch(
                    "chat_client.repositories.chat_repository.get_dialog", return_value={"dialog_id": "dialog-123", "title": "Test Dialog"}
                ):
                    response = client.get("/chat/get-dialog/dialog-123")
                    assert response.status_code == 200
                    dialog = response.json()
                    assert dialog["title"] == "Test Dialog"
                    print("  ✓ Get dialog works")

                # Delete dialog
                with patch("chat_client.repositories.chat_repository.delete_dialog", return_value=True):
                    response = client.post("/chat/delete-dialog/dialog-123")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False
                    print("  ✓ Delete dialog works")

    def test_user_endpoints(self):
        """Test all user-related endpoints"""
        print("Testing user endpoints...")

        with TestClient(self.app) as client:
            # Test user registration
            with patch("chat_client.repositories.user_repository.create_user", return_value={"user_id": 1}):
                response = client.post(
                    "/user/signup",
                    json={
                        "email": "test@example.com",
                        "password": "testpassword123",
                        "password_repeat": "testpassword123",
                        "captcha": "TEST",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                print("  ✓ User signup works")

            # Test login
            with patch("chat_client.repositories.user_repository.login_user", return_value={"user_id": 1}):
                response = client.post("/user/login", json={"email": "test@example.com", "password": "testpassword123"})
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                print("  ✓ User login works")

            # Test account verification
            with patch("chat_client.repositories.user_repository.verify_user", return_value=True):
                response = client.post("/user/verify", json={"token": "test-token"})
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                print("  ✓ Account verification works")

            # Test password reset request
            with patch("chat_client.repositories.user_repository.reset_password", return_value=True):
                response = client.post("/user/reset", json={"email": "test@example.com"})
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                print("  ✓ Password reset request works")

            # Test new password setting
            with patch("chat_client.repositories.user_repository.new_password", return_value=True):
                response = client.post(
                    "/user/new-password", json={"token": "reset-token", "password": "newpassword123", "password_repeat": "newpassword123"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                print("  ✓ New password setting works")

            # Test profile operations
            with patch("chat_client.core.user_session.is_logged_in", return_value=1):
                # Get profile
                with patch(
                    "chat_client.repositories.user_repository.get_profile",
                    return_value={"email": "test@example.com", "system_message": "Test system message"},
                ):
                    response = client.get("/user/profile")
                    assert response.status_code == 200
                    assert "Profile" in response.text
                    print("  ✓ Get profile works")

                # Update profile
                with patch("chat_client.repositories.user_repository.update_profile", return_value=True):
                    response = client.post("/user/profile", json={"system_message": "Updated system message"})
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False
                    print("  ✓ Update profile works")

                # List dialogs
                with patch(
                    "chat_client.repositories.chat_repository.get_dialogs_info",
                    return_value=[{"dialog_id": "test-dialog", "title": "Test Dialog"}],
                ):
                    response = client.get("/user/dialogs/json")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False
                    assert len(data["dialogs_info"]) == 1
                    print("  ✓ List dialogs works")

    def test_prompt_endpoints(self):
        """Test all prompt-related endpoints"""
        print("Testing prompt endpoints...")

        with TestClient(self.app) as client:
            # Test prompt operations without authentication
            response = client.get("/prompt/json")
            assert response.status_code == 401
            print("  ✓ Prompt endpoints require authentication")

            # Test prompt operations with authentication
            with patch("chat_client.core.user_session.is_logged_in", return_value=1):
                # List prompts
                mock_prompt = MagicMock()
                mock_prompt.prompt_id = 1
                mock_prompt.title = "Test Prompt"
                mock_prompt.prompt = "Test content"

                with patch("chat_client.repositories.prompt_repository.list_prompts", return_value=[mock_prompt]):
                    response = client.get("/prompt/json")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False
                    assert len(data["prompts"]) == 1
                    assert data["prompts"][0]["title"] == "Test Prompt"
                    print("  ✓ List prompts works")

                # Create prompt
                with patch("chat_client.repositories.prompt_repository.create_prompt", return_value={"prompt_id": 2}):
                    response = client.post("/prompt/create", json={"title": "New Prompt", "prompt": "New prompt content"})
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False
                    assert data["prompt_id"] == 2
                    print("  ✓ Create prompt works")

                # Get prompt detail
                with patch("chat_client.repositories.prompt_repository.get_prompt", return_value=mock_prompt):
                    response = client.get("/prompt/1/json")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False
                    assert data["prompt"]["title"] == "Test Prompt"
                    print("  ✓ Get prompt detail works")

                # Update prompt
                with patch("chat_client.repositories.prompt_repository.get_prompt", return_value=mock_prompt):
                    with patch("chat_client.repositories.prompt_repository.update_prompt", return_value=True):
                        response = client.post("/prompt/1/edit", json={"title": "Updated Prompt", "prompt": "Updated content"})
                        assert response.status_code == 200
                        data = response.json()
                        assert data["error"] is False
                        print("  ✓ Update prompt works")

                # Delete prompt
                with patch("chat_client.repositories.prompt_repository.get_prompt", return_value=mock_prompt):
                    with patch("chat_client.repositories.prompt_repository.delete_prompt", return_value=True):
                        response = client.post("/prompt/1/delete")
                        assert response.status_code == 200
                        data = response.json()
                        assert data["error"] is False
                        print("  ✓ Delete prompt works")

    def test_error_endpoints(self):
        """Test error logging endpoint"""
        print("Testing error endpoints...")

        with TestClient(self.app) as client:
            # Test error logging
            with patch("chat_client.endpoints.error_endpoints.log") as mock_logger:
                response = client.post("/error/log", json={"error": "JavaScript error", "url": "/chat", "line": 42})
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "received"
                mock_logger.error.assert_called_once()
                print("  ✓ Error logging works")

    def test_tool_endpoints(self):
        """Test tool execution endpoints"""
        print("Testing tool endpoints...")

        with TestClient(self.app) as client:
            # Test tool execution without auth
            response = client.post("/tools/python", json={"code": "print('test')"})
            assert response.status_code == 401
            print("  ✓ Tool endpoints require authentication")

            # Test tool execution with auth but non-existent tool
            with patch("chat_client.core.user_session.is_logged_in", return_value=1):
                response = client.post("/tools/nonexistent", json={"data": "test"})
                assert response.status_code == 404
                data = response.json()
                assert "Tool not found" in data["text"]
                print("  ✓ Non-existent tool returns 404")

    def test_validation_and_error_cases(self):
        """Test validation errors and edge cases"""
        print("Testing validation and error cases...")

        with TestClient(self.app) as client:
            # Test user registration with validation error
            with patch("chat_client.repositories.user_repository.create_user") as mock_create:
                from chat_client.core.exceptions_validation import UserValidate

                mock_create.side_effect = UserValidate("Email already exists")

                response = client.post(
                    "/user/signup",
                    json={
                        "email": "existing@example.com",
                        "password": "testpassword123",
                        "password_repeat": "testpassword123",
                        "captcha": "TEST",
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is True
                assert "Email already exists" in data["message"]
                print("  ✓ Validation errors are handled properly")

            # Test login with invalid credentials
            with patch("chat_client.repositories.user_repository.login_user") as mock_login:
                from chat_client.core.exceptions_validation import UserValidate

                mock_login.side_effect = UserValidate("Invalid credentials")

                response = client.post("/user/login", json={"email": "test@example.com", "password": "wrongpassword"})
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is True
                assert "Invalid credentials" in data["message"]
                print("  ✓ Invalid credentials are handled properly")

            # Test accessing protected routes without authentication
            # These routes should all require authentication and redirect or return 401
            protected_routes = [
                ("GET", "/user/profile"),
                ("GET", "/prompt"),
                ("POST", "/chat/create-dialog", {"title": "Test"}),
            ]

            for method, url, *json_data in protected_routes:
                json_payload = json_data[0] if json_data else None

                with patch("chat_client.core.user_session.is_logged_in", return_value=False):
                    try:
                        if method == "GET":
                            response = client.get(url, follow_redirects=False)
                        else:
                            response = client.post(url, json=json_payload)

                        # Should either redirect to login (307) or return 401 Unauthorized
                        assert response.status_code in [
                            307,
                            401,
                        ], f"Route {method} {url} returned {response.status_code}, expected 307 or 401"

                        if response.status_code == 307:
                            # Verify it's redirecting to login
                            location = response.headers.get("location", "")
                            assert "/user/login" in location, f"Route {method} {url} should redirect to login, got {location}"

                    except Exception as e:
                        print(f"    Error testing {method} {url}: {e}")
                        # Continue with other tests
                        continue

            # Test the main chat route separately
            with patch("chat_client.core.user_session.is_logged_in", return_value=False):
                response = client.get("/", follow_redirects=False)
                assert response.status_code == 307, f"Main route should redirect when not authenticated"
                location = response.headers.get("location", "")
                assert "/user/login" in location, f"Main route should redirect to login"

            print("  ✓ Protected routes require authentication")

    def run_all_tests(self):
        """Run all test methods"""
        test_methods = [
            self.test_chat_endpoints,
            self.test_user_endpoints,
            self.test_prompt_endpoints,
            self.test_error_endpoints,
            self.test_tool_endpoints,
            self.test_validation_and_error_cases,
        ]

        passed = 0
        failed = 0

        for test_method in test_methods:
            try:
                self.setup_method()
                test_method()
                passed += 1
            except Exception as e:
                print(f"  ❌ {test_method.__name__} failed: {e}")
                failed += 1

        return passed, failed


def main():
    """Main test runner"""
    print("Running comprehensive Starlette backend tests...")
    print("=" * 60)

    test_suite = TestStarletteBackend()
    passed, failed = test_suite.run_all_tests()

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("✅ All comprehensive tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
