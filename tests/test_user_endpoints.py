"""
Tests for user endpoints (authentication, registration, profile, etc.)
"""
import json
from unittest.mock import patch, MagicMock

from tests.test_base import BaseTestCase, run_async_test


class TestUserEndpoints(BaseTestCase):
    """Test user-related endpoints"""

    def test_signup_get(self):
        """Test GET /user/signup"""
        response = self.client.get("/user/signup")
        assert response.status_code == 200
        assert "Sign up" in response.text

    def test_signup_post_success(self):
        """Test successful user registration"""
        # Mock captcha session
        with patch('starlette.requests.Request.session', new_callable=lambda: {'captcha': 'TEST'}):
            # Mock user repository create_user
            with patch('chat_client.repositories.user_repository.create_user') as mock_create:
                mock_create.return_value = {"user_id": 1}
                
                response = self.client.post("/user/signup", json={
                    "email": "test@example.com",
                    "password": "testpassword123",
                    "password_repeat": "testpassword123",
                    "captcha": "TEST"
                })
                
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                assert "account has been created" in data["message"]

    def test_signup_post_validation_error(self):
        """Test user registration with validation error"""
        with patch('starlette.requests.Request.session', new_callable=lambda: {'captcha': 'TEST'}):
            # Mock validation error
            with patch('chat_client.repositories.user_repository.create_user') as mock_create:
                from chat_client.core.exceptions_validation import UserValidate
                mock_create.side_effect = UserValidate("Email already exists")
                
                response = self.client.post("/user/signup", json={
                    "email": "test@example.com",
                    "password": "testpassword123",
                    "password_repeat": "testpassword123",
                    "captcha": "TEST"
                })
                
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is True
                assert "Email already exists" in data["message"]

    def test_login_get(self):
        """Test GET /user/login"""
        response = self.client.get("/user/login")
        assert response.status_code == 200
        assert "Login" in response.text

    def test_login_post_success(self):
        """Test successful login"""
        with patch('chat_client.repositories.user_repository.login_user') as mock_login:
            mock_login.return_value = {"user_id": 1}
            
            response = self.client.post("/user/login", json={
                "email": "test@example.com",
                "password": "testpassword123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is False

    def test_login_post_invalid_credentials(self):
        """Test login with invalid credentials"""
        with patch('chat_client.repositories.user_repository.login_user') as mock_login:
            from chat_client.core.exceptions_validation import UserValidate
            mock_login.side_effect = UserValidate("Invalid credentials")
            
            response = self.client.post("/user/login", json={
                "email": "test@example.com",
                "password": "wrongpassword"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is True
            assert "Invalid credentials" in data["message"]

    def test_verify_get(self):
        """Test GET /user/verify with token"""
        response = self.client.get("/user/verify?token=test-token")
        assert response.status_code == 200
        assert "Verify account" in response.text

    def test_verify_post_success(self):
        """Test successful account verification"""
        with patch('chat_client.repositories.user_repository.verify_user') as mock_verify:
            mock_verify.return_value = True
            
            response = self.client.post("/user/verify", json={
                "token": "valid-token"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is False

    def test_verify_post_invalid_token(self):
        """Test account verification with invalid token"""
        with patch('chat_client.repositories.user_repository.verify_user') as mock_verify:
            from chat_client.core.exceptions_validation import UserValidate
            mock_verify.side_effect = UserValidate("Invalid token")
            
            response = self.client.post("/user/verify", json={
                "token": "invalid-token"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is True
            assert "Invalid token" in data["message"]

    def test_logout_get(self):
        """Test GET /user/logout"""
        response = self.client.get("/user/logout")
        assert response.status_code == 200
        assert "Logout" in response.text

    def test_logout_with_logout_param(self):
        """Test logout with logout parameter"""
        with patch('chat_client.core.user_session.clear_user_session') as mock_clear:
            response = self.client.get("/user/logout?logout=1")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_logout_with_logout_all_param(self):
        """Test logout all devices"""
        with patch('chat_client.core.user_session.clear_user_session') as mock_clear:
            response = self.client.get("/user/logout?logout_all=1")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_captcha_endpoint(self):
        """Test captcha image generation"""
        response = self.client.get("/captcha")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_reset_password_get(self):
        """Test GET /user/reset"""
        response = self.client.get("/user/reset")
        assert response.status_code == 200
        assert "Reset password" in response.text

    def test_reset_password_post_success(self):
        """Test successful password reset request"""
        with patch('chat_client.repositories.user_repository.reset_password') as mock_reset:
            mock_reset.return_value = True
            
            response = self.client.post("/user/reset", json={
                "email": "test@example.com"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is False
            assert "password reset email has been sent" in data["message"]

    def test_reset_password_post_user_not_found(self):
        """Test password reset for non-existent user"""
        with patch('chat_client.repositories.user_repository.reset_password') as mock_reset:
            from chat_client.core.exceptions_validation import UserValidate
            mock_reset.side_effect = UserValidate("User not found")
            
            response = self.client.post("/user/reset", json={
                "email": "nonexistent@example.com"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is True
            assert "User not found" in data["message"]

    def test_new_password_get(self):
        """Test GET /user/new-password with token"""
        response = self.client.get("/user/new-password?token=test-token")
        assert response.status_code == 200
        assert "New password" in response.text

    def test_new_password_post_success(self):
        """Test successful password update"""
        with patch('chat_client.repositories.user_repository.new_password') as mock_new_pass:
            mock_new_pass.return_value = True
            
            response = self.client.post("/user/new-password", json={
                "token": "valid-token",
                "password": "newpassword123",
                "password_repeat": "newpassword123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is False

    def test_is_logged_in_not_authenticated(self):
        """Test /user/is-logged-in when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/user/is-logged-in")
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is True
            assert data["redirect"] == "/user/login"

    def test_is_logged_in_authenticated(self):
        """Test /user/is-logged-in when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = 1  # User ID
            
            response = self.client.get("/user/is-logged-in")
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is False
            assert "logged in" in data["message"]

    def test_profile_get_not_authenticated(self):
        """Test GET /user/profile when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/user/profile")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_profile_get_authenticated(self):
        """Test GET /user/profile when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.user_repository.get_profile') as mock_get_profile:
                mock_logged_in.return_value = 1
                mock_get_profile.return_value = {
                    "email": "test@example.com",
                    "system_message": "Test system message"
                }
                
                response = self.client.get("/user/profile")
                assert response.status_code == 200
                assert "Profile" in response.text

    def test_profile_post_success(self):
        """Test successful profile update"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.user_repository.update_profile') as mock_update:
                mock_logged_in.return_value = 1
                mock_update.return_value = True
                
                response = self.client.post("/user/profile", json={
                    "system_message": "Updated system message"
                })
                
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False

    def test_list_dialogs_not_authenticated(self):
        """Test /user/dialogs when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/user/dialogs")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_list_dialogs_authenticated(self):
        """Test /user/dialogs when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = 1
            
            response = self.client.get("/user/dialogs")
            assert response.status_code == 200
            assert "Search dialogs" in response.text

    def test_list_dialogs_json_not_authenticated(self):
        """Test /user/dialogs/json when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/user/dialogs/json")
            assert response.status_code == 200
            data = response.json()
            assert data["error"] is True
            assert "logged out" in data["message"]

    def test_list_dialogs_json_authenticated(self):
        """Test /user/dialogs/json when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.chat_repository.get_dialogs_info') as mock_get_dialogs:
                mock_logged_in.return_value = 1
                mock_get_dialogs.return_value = [
                    {"dialog_id": "test-dialog", "title": "Test Dialog"}
                ]
                
                response = self.client.get("/user/dialogs/json")
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                assert len(data["dialogs_info"]) == 1