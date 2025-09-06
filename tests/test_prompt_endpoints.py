"""
Tests for prompt endpoints (CRUD operations for user prompts)
"""
import json
from unittest.mock import patch, MagicMock

from tests.test_base import BaseTestCase


class TestPromptEndpoints(BaseTestCase):
    """Test prompt-related endpoints"""

    def test_prompt_list_get_not_authenticated(self):
        """Test GET /prompt when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/prompt")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_prompt_list_get_authenticated(self):
        """Test GET /prompt when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.list_prompts') as mock_list:
                mock_logged_in.return_value = 1
                mock_list.return_value = [
                    MagicMock(prompt_id=1, title="Test Prompt", prompt="Test content")
                ]
                
                response = self.client.get("/prompt")
                assert response.status_code == 200
                assert "Your Prompts" in response.text

    def test_prompt_list_json_not_authenticated(self):
        """Test GET /prompt/json when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/prompt/json")
            assert response.status_code == 401
            data = response.json()
            assert data["error"] is True
            assert "Not authenticated" in data["message"]

    def test_prompt_list_json_authenticated(self):
        """Test GET /prompt/json when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.list_prompts') as mock_list:
                mock_logged_in.return_value = 1
                
                # Mock prompt objects
                mock_prompt = MagicMock()
                mock_prompt.prompt_id = 1
                mock_prompt.title = "Test Prompt"
                mock_prompt.prompt = "Test content"
                mock_list.return_value = [mock_prompt]
                
                response = self.client.get("/prompt/json")
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                assert len(data["prompts"]) == 1
                assert data["prompts"][0]["title"] == "Test Prompt"

    def test_prompt_create_get_not_authenticated(self):
        """Test GET /prompt/create when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/prompt/create")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_prompt_create_get_authenticated(self):
        """Test GET /prompt/create when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = 1
            
            response = self.client.get("/prompt/create")
            assert response.status_code == 200
            assert "Create Prompt" in response.text

    def test_prompt_create_post_not_authenticated(self):
        """Test POST /prompt/create when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.post("/prompt/create", json={
                "title": "Test Prompt",
                "prompt": "Test content"
            })
            
            assert response.status_code == 401
            data = response.json()
            assert data["error"] is True
            assert "Not authenticated" in data["message"]

    def test_prompt_create_post_authenticated(self):
        """Test POST /prompt/create when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.create_prompt') as mock_create:
                mock_logged_in.return_value = 1
                mock_create.return_value = {"prompt_id": 1}
                
                response = self.client.post("/prompt/create", json={
                    "title": "Test Prompt",
                    "prompt": "Test content"
                })
                
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                assert data["prompt_id"] == 1

    def test_prompt_create_post_validation_error(self):
        """Test POST /prompt/create with validation error"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.create_prompt') as mock_create:
                mock_logged_in.return_value = 1
                from chat_client.core.exceptions_validation import UserValidate
                mock_create.side_effect = UserValidate("Title is required")
                
                response = self.client.post("/prompt/create", json={
                    "title": "",
                    "prompt": "Test content"
                })
                
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is True
                assert "Title is required" in data["message"]

    def test_prompt_detail_not_authenticated(self):
        """Test GET /prompt/{prompt_id} when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/prompt/1")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_prompt_detail_authenticated(self):
        """Test GET /prompt/{prompt_id} when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                mock_logged_in.return_value = 1
                mock_prompt = MagicMock()
                mock_prompt.title = "Test Prompt"
                mock_prompt.prompt = "Test content"
                mock_get.return_value = mock_prompt
                
                response = self.client.get("/prompt/1")
                assert response.status_code == 200
                assert "Test Prompt" in response.text

    def test_prompt_detail_not_found(self):
        """Test GET /prompt/{prompt_id} when prompt not found"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                mock_logged_in.return_value = 1
                from chat_client.core.exceptions_validation import UserValidate
                mock_get.side_effect = UserValidate("Prompt not found")
                
                response = self.client.get("/prompt/999")
                assert response.status_code == 307  # Redirect
                assert response.headers["location"] == "/prompt"

    def test_prompt_detail_json_not_authenticated(self):
        """Test GET /prompt/{prompt_id}/json when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/prompt/1/json")
            assert response.status_code == 401
            data = response.json()
            assert data["error"] is True

    def test_prompt_detail_json_authenticated(self):
        """Test GET /prompt/{prompt_id}/json when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                mock_logged_in.return_value = 1
                mock_prompt = MagicMock()
                mock_prompt.prompt_id = 1
                mock_prompt.title = "Test Prompt"
                mock_prompt.prompt = "Test content"
                mock_get.return_value = mock_prompt
                
                response = self.client.get("/prompt/1/json")
                assert response.status_code == 200
                data = response.json()
                assert data["error"] is False
                assert data["prompt"]["title"] == "Test Prompt"

    def test_prompt_detail_json_not_found(self):
        """Test GET /prompt/{prompt_id}/json when prompt not found"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                mock_logged_in.return_value = 1
                from chat_client.core.exceptions_validation import UserValidate
                mock_get.side_effect = UserValidate("Prompt not found")
                
                response = self.client.get("/prompt/999/json")
                assert response.status_code == 404
                data = response.json()
                assert data["error"] is True
                assert "Prompt not found" in data["message"]

    def test_prompt_edit_get_not_authenticated(self):
        """Test GET /prompt/{prompt_id}/edit when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.get("/prompt/1/edit")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_prompt_edit_get_authenticated(self):
        """Test GET /prompt/{prompt_id}/edit when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                mock_logged_in.return_value = 1
                mock_prompt = MagicMock()
                mock_prompt.title = "Test Prompt"
                mock_prompt.prompt = "Test content"
                mock_get.return_value = mock_prompt
                
                response = self.client.get("/prompt/1/edit")
                assert response.status_code == 200
                assert "Edit Test Prompt" in response.text

    def test_prompt_edit_get_not_found(self):
        """Test GET /prompt/{prompt_id}/edit when prompt not found"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                mock_logged_in.return_value = 1
                from chat_client.core.exceptions_validation import UserValidate
                mock_get.side_effect = UserValidate("Prompt not found")
                
                response = self.client.get("/prompt/999/edit")
                assert response.status_code == 307  # Redirect
                assert response.headers["location"] == "/prompt"

    def test_prompt_edit_post_not_authenticated(self):
        """Test POST /prompt/{prompt_id}/edit when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.post("/prompt/1/edit", json={
                "title": "Updated Prompt",
                "prompt": "Updated content"
            })
            
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_prompt_edit_post_authenticated(self):
        """Test POST /prompt/{prompt_id}/edit when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                with patch('chat_client.repositories.prompt_repository.update_prompt') as mock_update:
                    mock_logged_in.return_value = 1
                    mock_prompt = MagicMock()
                    mock_get.return_value = mock_prompt
                    mock_update.return_value = True
                    
                    response = self.client.post("/prompt/1/edit", json={
                        "title": "Updated Prompt",
                        "prompt": "Updated content"
                    })
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False

    def test_prompt_edit_post_not_found(self):
        """Test POST /prompt/{prompt_id}/edit when prompt not found"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                mock_logged_in.return_value = 1
                mock_get.return_value = None
                
                response = self.client.post("/prompt/999/edit", json={
                    "title": "Updated Prompt",
                    "prompt": "Updated content"
                })
                
                assert response.status_code == 404
                data = response.json()
                assert data["error"] is True
                assert "Prompt not found" in data["message"]

    def test_prompt_edit_post_validation_error(self):
        """Test POST /prompt/{prompt_id}/edit with validation error"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                with patch('chat_client.repositories.prompt_repository.update_prompt') as mock_update:
                    mock_logged_in.return_value = 1
                    mock_prompt = MagicMock()
                    mock_get.return_value = mock_prompt
                    from chat_client.core.exceptions_validation import UserValidate
                    mock_update.side_effect = UserValidate("Title is required")
                    
                    response = self.client.post("/prompt/1/edit", json={
                        "title": "",
                        "prompt": "Updated content"
                    })
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is True
                    assert "Title is required" in data["message"]

    def test_prompt_delete_post_not_authenticated(self):
        """Test POST /prompt/{prompt_id}/delete when not authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            mock_logged_in.return_value = False
            
            response = self.client.post("/prompt/1/delete")
            assert response.status_code == 307  # Redirect
            assert response.headers["location"] == "/user/login"

    def test_prompt_delete_post_authenticated(self):
        """Test POST /prompt/{prompt_id}/delete when authenticated"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                with patch('chat_client.repositories.prompt_repository.delete_prompt') as mock_delete:
                    mock_logged_in.return_value = 1
                    mock_prompt = MagicMock()
                    mock_get.return_value = mock_prompt
                    mock_delete.return_value = True
                    
                    response = self.client.post("/prompt/1/delete")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is False

    def test_prompt_delete_post_not_found(self):
        """Test POST /prompt/{prompt_id}/delete when prompt not found"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                mock_logged_in.return_value = 1
                mock_get.return_value = None
                
                response = self.client.post("/prompt/999/delete")
                
                assert response.status_code == 404
                data = response.json()
                assert data["error"] is True
                assert "Prompt not found" in data["message"]

    def test_prompt_delete_post_validation_error(self):
        """Test POST /prompt/{prompt_id}/delete with validation error"""
        with patch('chat_client.core.user_session.is_logged_in') as mock_logged_in:
            with patch('chat_client.repositories.prompt_repository.get_prompt') as mock_get:
                with patch('chat_client.repositories.prompt_repository.delete_prompt') as mock_delete:
                    mock_logged_in.return_value = 1
                    mock_prompt = MagicMock()
                    mock_get.return_value = mock_prompt
                    from chat_client.core.exceptions_validation import UserValidate
                    mock_delete.side_effect = UserValidate("Cannot delete prompt")
                    
                    response = self.client.post("/prompt/1/delete")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["error"] is True
                    assert "Cannot delete prompt" in data["message"]