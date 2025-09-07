"""
Tests for chat endpoints (chat page, streaming, models, dialogs, messages)
"""
import json
from unittest.mock import patch, MagicMock

from tests.test_base import BaseTestCase, mock_openai_client, mock_llm_response


class TestChatEndpoints(BaseTestCase):
    """Test chat-related endpoints"""

    @patch('chat_client.core.user_session.is_logged_in')
    def test_chat_page_not_authenticated(self, mock_logged_in):
        """Test GET / when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.get("/")
        assert response.status_code == 307  # Redirect
        assert response.headers["location"] == "/user/login"

    @patch('chat_client.repositories.prompt_repository.list_prompts')
    @patch('chat_client.endpoints.chat_endpoints._get_model_names')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_chat_page_authenticated(self, mock_logged_in, mock_models, mock_prompts):
        """Test GET / when authenticated"""
        mock_logged_in.return_value = 1
        mock_models.return_value = ["test-model"]
        mock_prompts.return_value = []
        
        response = self.client.get("/")
        assert response.status_code == 200
        assert "Chat" in response.text

    @patch('chat_client.repositories.prompt_repository.list_prompts')
    @patch('chat_client.endpoints.chat_endpoints._get_model_names')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_chat_page_with_dialog_id(self, mock_logged_in, mock_models, mock_prompts):
        """Test GET /chat/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_models.return_value = ["test-model"]
        mock_prompts.return_value = []
        
        response = self.client.get("/chat/test-dialog-id")
        assert response.status_code == 200
        assert "Chat" in response.text

    def test_config_endpoint(self):
        """Test GET /config"""
        response = self.client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "default_model" in data
        assert "tools_callback" in data
        assert "use_katex" in data

    def test_list_models(self):
        """Test GET /list (available models)"""
        response = self.client.get("/list")
        assert response.status_code == 200
        data = response.json()
        assert "model_names" in data
        assert isinstance(data["model_names"], list)

    @patch('chat_client.core.user_session.is_logged_in')
    def test_chat_response_stream_not_authenticated(self, mock_logged_in):
        """Test POST /chat when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "test-model"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "must be logged in" in data["message"]

    @patch('openai.OpenAI')
    @patch('chat_client.repositories.user_repository.get_profile')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_chat_response_stream_authenticated(self, mock_logged_in, mock_profile, mock_openai_class):
        """Test POST /chat when authenticated"""
        mock_logged_in.return_value = 1
        mock_profile.return_value = {"system_message": ""}
        
        # Mock OpenAI client
        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client
        
        response = self.client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "test-model"
        })
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    @patch('chat_client.core.user_session.is_logged_in')
    def test_create_dialog_not_authenticated(self, mock_logged_in):
        """Test POST /chat/create-dialog when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.post("/chat/create-dialog", json={
            "title": "Test Dialog"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "must be logged in" in data["message"]

    @patch('chat_client.repositories.chat_repository.create_dialog')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_create_dialog_authenticated(self, mock_logged_in, mock_create):
        """Test POST /chat/create-dialog when authenticated"""
        mock_logged_in.return_value = 1
        mock_create.return_value = "test-dialog-id"
        
        response = self.client.post("/chat/create-dialog", json={
            "title": "Test Dialog"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["dialog_id"] == "test-dialog-id"

    @patch('chat_client.repositories.chat_repository.create_dialog')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_create_dialog_validation_error(self, mock_logged_in, mock_create):
        """Test POST /chat/create-dialog with validation error"""
        mock_logged_in.return_value = 1
        from chat_client.core.exceptions_validation import UserValidate
        mock_create.side_effect = UserValidate("Invalid title")
        
        response = self.client.post("/chat/create-dialog", json={
            "title": ""
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is True
        assert "Invalid title" in data["message"]

    @patch('chat_client.core.user_session.is_logged_in')
    def test_create_message_not_authenticated(self, mock_logged_in):
        """Test POST /chat/create-message/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.post("/chat/create-message/test-dialog", json={
            "content": "Test message",
            "role": "user"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch('chat_client.repositories.chat_repository.create_message')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_create_message_authenticated(self, mock_logged_in, mock_create):
        """Test POST /chat/create-message/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_create.return_value = 123  # message_id
        
        response = self.client.post("/chat/create-message/test-dialog", json={
            "content": "Test message",
            "role": "user"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == 123

    @patch('chat_client.core.user_session.is_logged_in')
    def test_get_dialog_not_authenticated(self, mock_logged_in):
        """Test GET /chat/get-dialog/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.get("/chat/get-dialog/test-dialog")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch('chat_client.repositories.chat_repository.get_dialog')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_get_dialog_authenticated(self, mock_logged_in, mock_get):
        """Test GET /chat/get-dialog/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_get.return_value = {
            "dialog_id": "test-dialog",
            "title": "Test Dialog",
            "user_id": 1
        }
        
        response = self.client.get("/chat/get-dialog/test-dialog")
        
        assert response.status_code == 200
        data = response.json()
        assert data["dialog_id"] == "test-dialog"
        assert data["title"] == "Test Dialog"

    @patch('chat_client.core.user_session.is_logged_in')
    def test_get_messages_not_authenticated(self, mock_logged_in):
        """Test GET /chat/get-messages/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.get("/chat/get-messages/test-dialog")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch('chat_client.repositories.chat_repository.get_messages')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_get_messages_authenticated(self, mock_logged_in, mock_get):
        """Test GET /chat/get-messages/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_get.return_value = [
            {
                "message_id": 1,
                "content": "Hello",
                "role": "user",
                "dialog_id": "test-dialog"
            }
        ]
        
        response = self.client.get("/chat/get-messages/test-dialog")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Hello"

    @patch('chat_client.core.user_session.is_logged_in')
    def test_update_message_not_authenticated(self, mock_logged_in):
        """Test POST /chat/update-message/{message_id} when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.post("/chat/update-message/1", json={
            "content": "Updated message"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch('chat_client.repositories.chat_repository.update_message')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_update_message_authenticated(self, mock_logged_in, mock_update):
        """Test POST /chat/update-message/{message_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_update.return_value = {"message_id": 1}
        
        response = self.client.post("/chat/update-message/1", json={
            "content": "Updated message"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["message_id"] == 1

    @patch('chat_client.core.user_session.is_logged_in')
    def test_delete_dialog_not_authenticated(self, mock_logged_in):
        """Test POST /chat/delete-dialog/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.post("/chat/delete-dialog/test-dialog")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch('chat_client.repositories.chat_repository.delete_dialog')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_delete_dialog_authenticated(self, mock_logged_in, mock_delete):
        """Test POST /chat/delete-dialog/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_delete.return_value = True
        
        response = self.client.post("/chat/delete-dialog/test-dialog")
        
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False

    @patch('chat_client.core.user_session.is_logged_in')
    def test_json_tools_not_authenticated(self, mock_logged_in):
        """Test POST /tools/{tool} when not authenticated"""
        mock_logged_in.return_value = False
        
        response = self.client.post("/tools/python", json={
            "code": "print('hello')"
        })
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "must be logged in" in data["message"]

    @patch('chat_client.core.user_session.is_logged_in')
    def test_json_tools_tool_not_found(self, mock_logged_in):
        """Test POST /tools/{tool} with non-existent tool"""
        mock_logged_in.return_value = 1
        
        response = self.client.post("/tools/nonexistent", json={
            "code": "print('hello')"
        })
        
        assert response.status_code == 404
        data = response.json()
        assert "Tool not found" in data["text"]

    @patch('builtins.__import__')
    @patch('chat_client.endpoints.chat_endpoints.config')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_json_tools_with_valid_tool(self, mock_logged_in, mock_config, mock_import):
        """Test POST /tools/{tool} with valid tool"""
        # Mock the tools callback configuration
        mock_tools_callback = {
            "python": {
                "module": "chat_client.tools.python_exec",
                "def": "execute"
            }
        }
        
        mock_logged_in.return_value = 1
        mock_config.TOOLS_CALLBACK = mock_tools_callback
        
        # Mock the module and function
        mock_module = MagicMock()
        mock_function = MagicMock()
        mock_function.return_value = "Hello World"
        mock_module.execute = mock_function
        mock_import.return_value = mock_module
        
        response = self.client.post("/tools/python", json={
            "code": "print('Hello World')"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["tool"] == "python"
        assert data["text"] == "Hello World"

    @patch('openai.OpenAI')
    @patch('chat_client.repositories.user_repository.get_profile')
    @patch('chat_client.core.user_session.is_logged_in')
    def test_chat_streaming_with_system_message(self, mock_logged_in, mock_profile, mock_openai_class):
        """Test chat streaming with system message in user profile"""
        mock_logged_in.return_value = 1
        mock_profile.return_value = {"system_message": "You are a helpful assistant."}
        
        # Mock OpenAI client
        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client
        
        response = self.client.post("/chat", json={
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "test-model"
        })
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Check that create was called with system message prepended
        args, kwargs = mock_client.chat.completions.create.call_args
        messages = kwargs["messages"]
        assert len(messages) == 2  # system message + user message
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "You are a helpful assistant."