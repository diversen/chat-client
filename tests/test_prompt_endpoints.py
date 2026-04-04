"""
Tests for prompt endpoints (CRUD operations for user prompts)
"""

import json
from unittest.mock import patch, MagicMock

from tests.test_base import BaseTestCase


class TestPromptEndpoints(BaseTestCase):
    """Test prompt-related endpoints"""

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_list_get_not_authenticated(self, mock_logged_in):
        """Test GET /prompts when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/prompts")
        assert response.status_code == 307  # Redirect
        assert response.headers["location"] == "/user/login"

    @patch("chat_client.repositories.prompt_repository.list_prompts")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_list_get_authenticated(self, mock_logged_in, mock_list):
        """Test GET /prompts when authenticated"""
        mock_logged_in.return_value = 1
        mock_list.return_value = [MagicMock(prompt_id=1, title="Test Prompt", prompt="Test content")]

        response = self.client.get("/prompts")
        assert response.status_code == 200
        assert "Your Prompts" in response.text

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_list_json_not_authenticated(self, mock_logged_in):
        """Test GET /api/prompts when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/api/prompts")
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "Not authenticated" in data["message"]

    @patch("chat_client.repositories.prompt_repository.list_prompts")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_list_json_authenticated(self, mock_logged_in, mock_list):
        """Test GET /api/prompts when authenticated"""
        mock_logged_in.return_value = 1

        # Mock prompt objects
        mock_prompt = MagicMock()
        mock_prompt.prompt_id = 1
        mock_prompt.title = "Test Prompt"
        mock_prompt.prompt = "Test content"
        mock_list.return_value = [mock_prompt]

        response = self.client.get("/api/prompts")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert len(data["prompts"]) == 1
        assert data["prompts"][0]["title"] == "Test Prompt"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_create_get_not_authenticated(self, mock_logged_in):
        """Test GET /prompts/new when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/prompts/new")
        assert response.status_code == 307  # Redirect
        assert response.headers["location"] == "/user/login"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_create_get_authenticated(self, mock_logged_in):
        """Test GET /prompts/new when authenticated"""
        mock_logged_in.return_value = 1

        response = self.client.get("/prompts/new")
        assert response.status_code == 200
        assert "New Custom Prompt" in response.text

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_create_post_not_authenticated(self, mock_logged_in):
        """Test POST /prompts/new when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/api/prompts", json={"title": "Test Prompt", "prompt": "Test content"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "Not authenticated" in data["message"]
        assert data["redirect"] == "/user/login?next=/prompts&reason=auth_required"

    @patch("chat_client.repositories.prompt_repository.create_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_create_post_authenticated(self, mock_logged_in, mock_create):
        """Test POST /prompts/new when authenticated"""
        mock_logged_in.return_value = 1
        mock_create.return_value = {"prompt_id": 1}

        response = self.client.post("/api/prompts", json={"title": "Test Prompt", "prompt": "Test content"})

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["prompt_id"] == 1
        assert data["message"] == "Prompt created successfully"

    @patch("chat_client.repositories.prompt_repository.create_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_create_post_validation_error(self, mock_logged_in, mock_create):
        """Test POST /prompts/new with validation error"""
        mock_logged_in.return_value = 1
        from chat_client.core.exceptions_validation import UserValidate

        mock_create.side_effect = UserValidate("Title is required")

        response = self.client.post("/api/prompts", json={"title": "", "prompt": "Test content"})

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert "Title is required" in data["message"]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_detail_not_authenticated(self, mock_logged_in):
        """Test GET /prompts/{prompt_id} when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/prompts/1")
        assert response.status_code == 307  # Redirect
        assert response.headers["location"] == "/user/login"

    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_detail_authenticated(self, mock_logged_in, mock_get):
        """Test GET /prompts/{prompt_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_prompt = MagicMock()
        mock_prompt.title = "Test Prompt"
        mock_prompt.prompt = "Test content"
        mock_get.return_value = mock_prompt

        response = self.client.get("/prompts/1")
        assert response.status_code == 200
        assert "Test Prompt" in response.text

    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_detail_not_found(self, mock_logged_in, mock_get):
        """Test GET /prompts/{prompt_id} when prompt not found"""
        mock_logged_in.return_value = 1
        from chat_client.core.exceptions_validation import UserValidate

        mock_get.side_effect = UserValidate("Prompt not found")

        response = self.client.get("/prompts/999")
        assert response.status_code == 307  # Redirect
        assert response.headers["location"] == "/prompts"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_detail_json_not_authenticated(self, mock_logged_in):
        """Test GET /prompts/{prompt_id}/json when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/api/prompts/1")
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/prompts&reason=auth_required"

    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_detail_json_authenticated(self, mock_logged_in, mock_get):
        """Test GET /prompts/{prompt_id}/json when authenticated"""
        mock_logged_in.return_value = 1
        mock_prompt = MagicMock()
        mock_prompt.prompt_id = 1
        mock_prompt.title = "Test Prompt"
        mock_prompt.prompt = "Test content"
        mock_get.return_value = mock_prompt

        response = self.client.get("/api/prompts/1")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["prompt"]["title"] == "Test Prompt"

    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_detail_json_not_found(self, mock_logged_in, mock_get):
        """Test GET /prompts/{prompt_id}/json when prompt not found"""
        mock_logged_in.return_value = 1
        from chat_client.core.exceptions_validation import UserValidate

        mock_get.side_effect = UserValidate("Prompt not found")

        response = self.client.get("/api/prompts/999")
        assert response.status_code == 404
        data = response.json()
        assert data["error"] is True
        assert "Prompt not found" in data["message"]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_edit_get_not_authenticated(self, mock_logged_in):
        """Test GET /prompts/{prompt_id}/edit when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/prompts/1/edit")
        assert response.status_code == 307  # Redirect
        assert response.headers["location"] == "/user/login"

    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_edit_get_authenticated(self, mock_logged_in, mock_get):
        """Test GET /prompts/{prompt_id}/edit when authenticated"""
        mock_logged_in.return_value = 1
        mock_prompt = MagicMock()
        mock_prompt.title = "Test Prompt"
        mock_prompt.prompt = "Test content"
        mock_get.return_value = mock_prompt

        response = self.client.get("/prompts/1/edit")
        assert response.status_code == 200
        assert "Edit Test Prompt" in response.text

    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_edit_get_not_found(self, mock_logged_in, mock_get):
        """Test GET /prompts/{prompt_id}/edit when prompt not found"""
        mock_logged_in.return_value = 1
        from chat_client.core.exceptions_validation import UserValidate

        mock_get.side_effect = UserValidate("Prompt not found")

        response = self.client.get("/prompts/999/edit")
        assert response.status_code == 307  # Redirect
        assert response.headers["location"] == "/prompts"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_edit_post_not_authenticated(self, mock_logged_in):
        """Test POST /prompts/{prompt_id}/edit when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/api/prompts/1", json={"title": "Updated Prompt", "prompt": "Updated content"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/prompts&reason=auth_required"

    @patch("chat_client.repositories.prompt_repository.update_prompt")
    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_edit_post_authenticated(self, mock_logged_in, mock_get, mock_update):
        """Test POST /prompts/{prompt_id}/edit when authenticated"""
        mock_logged_in.return_value = 1
        mock_prompt = MagicMock()
        mock_get.return_value = mock_prompt
        mock_update.return_value = True

        response = self.client.post("/api/prompts/1", json={"title": "Updated Prompt", "prompt": "Updated content"})

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["message"] == "Prompt updated successfully"

    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_edit_post_not_found(self, mock_logged_in, mock_get):
        """Test POST /prompts/{prompt_id}/edit when prompt not found"""
        mock_logged_in.return_value = 1
        mock_get.return_value = None

        response = self.client.post("/api/prompts/999", json={"title": "Updated Prompt", "prompt": "Updated content"})

        assert response.status_code == 404
        data = response.json()
        assert data["error"] is True
        assert "Prompt not found" in data["message"]

    @patch("chat_client.repositories.prompt_repository.update_prompt")
    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_edit_post_validation_error(self, mock_logged_in, mock_get, mock_update):
        """Test POST /prompts/{prompt_id}/edit with validation error"""
        mock_logged_in.return_value = 1
        mock_prompt = MagicMock()
        mock_get.return_value = mock_prompt
        from chat_client.core.exceptions_validation import UserValidate

        mock_update.side_effect = UserValidate("Title is required")

        response = self.client.post("/api/prompts/1", json={"title": "", "prompt": "Updated content"})

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert "Title is required" in data["message"]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_delete_post_not_authenticated(self, mock_logged_in):
        """Test POST /prompts/{prompt_id}/delete when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.request("DELETE", "/api/prompts/1")
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/prompts&reason=auth_required"

    @patch("chat_client.repositories.prompt_repository.delete_prompt")
    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_delete_post_authenticated(self, mock_logged_in, mock_get, mock_delete):
        """Test POST /prompts/{prompt_id}/delete when authenticated"""
        mock_logged_in.return_value = 1
        mock_prompt = MagicMock()
        mock_get.return_value = mock_prompt
        mock_delete.return_value = True

        response = self.client.request("DELETE", "/api/prompts/1")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False

    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_delete_post_not_found(self, mock_logged_in, mock_get):
        """Test POST /prompts/{prompt_id}/delete when prompt not found"""
        mock_logged_in.return_value = 1
        mock_get.return_value = None

        response = self.client.request("DELETE", "/api/prompts/999")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] is True
        assert "Prompt not found" in data["message"]

    @patch("chat_client.repositories.prompt_repository.delete_prompt")
    @patch("chat_client.repositories.prompt_repository.get_prompt")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_prompt_delete_post_validation_error(self, mock_logged_in, mock_get, mock_delete):
        """Test POST /prompts/{prompt_id}/delete with validation error"""
        mock_logged_in.return_value = 1
        mock_prompt = MagicMock()
        mock_get.return_value = mock_prompt
        from chat_client.core.exceptions_validation import UserValidate

        mock_delete.side_effect = UserValidate("Cannot delete prompt")

        response = self.client.request("DELETE", "/api/prompts/1")

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert "Cannot delete prompt" in data["message"]
