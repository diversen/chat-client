"""
Tests for chat endpoints (chat page, streaming, models, dialogs, messages)
"""

from unittest.mock import patch

from tests.test_base import BaseTestCase, mock_openai_client


class TestChatEndpoints(BaseTestCase):
    """Test chat-related endpoints"""

    def test_normalize_chat_messages_with_images(self):
        """User messages with images should be converted to OpenAI content parts"""
        from chat_client.endpoints.chat_endpoints import _normalize_chat_messages

        messages = [
            {
                "role": "user",
                "content": "Describe this image",
                "images": [{"data_url": "data:image/png;base64,AAAA"}],
            }
        ]
        normalized = _normalize_chat_messages(messages)

        assert len(normalized) == 1
        assert normalized[0]["role"] == "user"
        assert isinstance(normalized[0]["content"], list)
        assert normalized[0]["content"][0]["type"] == "text"
        assert normalized[0]["content"][1]["type"] == "image_url"

    @patch("chat_client.endpoints.chat_endpoints.PROVIDERS", {"local": {"api_key": "key", "base_url": "http://x"}})
    def test_resolve_provider_info_handles_string_dict_and_unknown_models(self):
        from chat_client.endpoints.chat_endpoints import _resolve_provider_info

        with patch("chat_client.endpoints.chat_endpoints.MODELS", {"m1": "local", "m2": {"provider": "local"}}):
            m1 = _resolve_provider_info("m1")
            m2 = _resolve_provider_info("m2")
            m3 = _resolve_provider_info("missing")

        assert m1["api_key"] == "key"
        assert m2["api_key"] == "key"
        assert m3 == {}

    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_page_not_authenticated(self, mock_logged_in):
        """Test GET / when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/")
        assert response.status_code == 307  # Redirect
        assert response.headers["location"] == "/user/login"

    @patch("chat_client.repositories.prompt_repository.list_prompts")
    @patch("chat_client.endpoints.chat_endpoints._get_model_names")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_page_authenticated(self, mock_logged_in, mock_models, mock_prompts):
        """Test GET / when authenticated"""
        mock_logged_in.return_value = 1
        mock_models.return_value = ["test-model"]
        mock_prompts.return_value = []

        response = self.client.get("/")
        assert response.status_code == 200
        assert "Chat" in response.text

    @patch("chat_client.repositories.prompt_repository.list_prompts")
    @patch("chat_client.endpoints.chat_endpoints._get_model_names")
    @patch("chat_client.core.user_session.is_logged_in")
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
        assert "use_katex" in data
        assert "show_mcp_tool_calls" in data
        assert "system_message_models" in data
        assert "vision_models" in data

    def test_list_models(self):
        """Test GET /list (available models)"""
        response = self.client.get("/list")
        assert response.status_code == 200
        data = response.json()
        assert "model_names" in data
        assert isinstance(data["model_names"], list)

    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_not_authenticated(self, mock_logged_in):
        """Test POST /chat when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}], "model": "test-model"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "must be logged in" in data["message"]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_validation_error(self, mock_logged_in):
        """Test POST /chat returns 400 on invalid payload"""
        mock_logged_in.return_value = 1

        response = self.client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True

    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_authenticated(self, mock_logged_in, mock_openai_class):
        """Test POST /chat when authenticated"""
        mock_logged_in.return_value = 1

        # Mock OpenAI client
        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client

        response = self.client.post("/chat", json={"messages": [{"role": "user", "content": "Hello"}], "model": "test-model"})

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    @patch("chat_client.endpoints.chat_endpoints.VISION_MODELS", ["test-model"])
    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_with_images(self, mock_logged_in, mock_openai_class):
        """Test POST /chat converts uploaded images into model content parts"""
        mock_logged_in.return_value = 1

        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client

        response = self.client.post(
            "/chat",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "Describe this",
                        "images": [
                            {"data_url": "data:image/png;base64,AAAA"},
                        ],
                    }
                ],
                "model": "test-model",
            },
        )

        assert response.status_code == 200
        _ = response.content
        called_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert called_messages[0]["role"] == "user"
        assert isinstance(called_messages[0]["content"], list)
        assert called_messages[0]["content"][0]["type"] == "text"
        assert called_messages[0]["content"][1]["type"] == "image_url"

    @patch("chat_client.endpoints.chat_endpoints.VISION_MODELS", [])
    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_with_images_strips_for_non_vision_model(self, mock_logged_in, mock_openai_class):
        """Test POST /chat strips image uploads when model is not vision-enabled"""
        mock_logged_in.return_value = 1

        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client

        response = self.client.post(
            "/chat",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "Describe this",
                        "images": [
                            {"data_url": "data:image/png;base64,AAAA"},
                        ],
                    }
                ],
                "model": "test-model",
            },
        )

        assert response.status_code == 200
        _ = response.content
        called_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert called_messages[0]["role"] == "user"
        assert called_messages[0]["content"] == "Describe this"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_dialog_not_authenticated(self, mock_logged_in):
        """Test POST /chat/create-dialog when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/chat/create-dialog", json={"title": "Test Dialog"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "must be logged in" in data["message"]

    @patch("chat_client.repositories.chat_repository.create_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_dialog_authenticated(self, mock_logged_in, mock_create):
        """Test POST /chat/create-dialog when authenticated"""
        mock_logged_in.return_value = 1
        mock_create.return_value = "test-dialog-id"

        response = self.client.post("/chat/create-dialog", json={"title": "Test Dialog"})

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["dialog_id"] == "test-dialog-id"

    @patch("chat_client.repositories.chat_repository.create_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_dialog_validation_error(self, mock_logged_in, mock_create):
        """Test POST /chat/create-dialog with validation error"""
        mock_logged_in.return_value = 1
        from chat_client.core.exceptions_validation import UserValidate

        mock_create.side_effect = UserValidate("Invalid title")

        response = self.client.post("/chat/create-dialog", json={"title": ""})

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert "Invalid title" in data["message"]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_message_not_authenticated(self, mock_logged_in):
        """Test POST /chat/create-message/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/chat/create-message/test-dialog", json={"content": "Test message", "role": "user"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch("chat_client.endpoints.chat_endpoints.VISION_MODELS", ["test-model"])
    @patch("chat_client.repositories.chat_repository.create_message")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_message_authenticated(self, mock_logged_in, mock_create):
        """Test POST /chat/create-message/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_create.return_value = 123  # message_id

        response = self.client.post(
            "/chat/create-message/test-dialog",
            json={
                "content": "Test message",
                "role": "user",
                "model": "test-model",
                "images": [{"data_url": "data:image/png;base64,AAAA"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message_id"] == 123
        mock_create.assert_called_once_with(
            1,
            "test-dialog",
            "user",
            "Test message",
            [{"data_url": "data:image/png;base64,AAAA"}],
        )

    @patch("chat_client.endpoints.chat_endpoints.VISION_MODELS", [])
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_message_rejects_non_vision_model_when_images_present(self, mock_logged_in):
        """Test POST /chat/create-message/{dialog_id} rejects images for non-vision model"""
        mock_logged_in.return_value = 1

        response = self.client.post(
            "/chat/create-message/test-dialog",
            json={
                "content": "Test message",
                "role": "user",
                "model": "test-model",
                "images": [{"data_url": "data:image/png;base64,AAAA"}],
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert "does not support image inputs" in data["message"]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_dialog_not_authenticated(self, mock_logged_in):
        """Test GET /chat/get-dialog/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/chat/get-dialog/test-dialog")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch("chat_client.repositories.chat_repository.get_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_dialog_authenticated(self, mock_logged_in, mock_get):
        """Test GET /chat/get-dialog/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_get.return_value = {"dialog_id": "test-dialog", "title": "Test Dialog", "user_id": 1}

        response = self.client.get("/chat/get-dialog/test-dialog")

        assert response.status_code == 200
        data = response.json()
        assert data["dialog_id"] == "test-dialog"
        assert data["title"] == "Test Dialog"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_messages_not_authenticated(self, mock_logged_in):
        """Test GET /chat/get-messages/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/chat/get-messages/test-dialog")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch("chat_client.repositories.chat_repository.get_messages")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_messages_authenticated(self, mock_logged_in, mock_get):
        """Test GET /chat/get-messages/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_get.return_value = [{"message_id": 1, "content": "Hello", "role": "user", "dialog_id": "test-dialog"}]

        response = self.client.get("/chat/get-messages/test-dialog")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Hello"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_update_message_not_authenticated(self, mock_logged_in):
        """Test POST /chat/update-message/{message_id} when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/chat/update-message/1", json={"content": "Updated message"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch("chat_client.repositories.chat_repository.update_message")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_update_message_authenticated(self, mock_logged_in, mock_update):
        """Test POST /chat/update-message/{message_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_update.return_value = {"message_id": 1}

        response = self.client.post("/chat/update-message/1", json={"content": "Updated message"})

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["message_id"] == 1

    @patch("chat_client.core.user_session.is_logged_in")
    def test_delete_dialog_not_authenticated(self, mock_logged_in):
        """Test POST /chat/delete-dialog/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/chat/delete-dialog/test-dialog")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch("chat_client.repositories.chat_repository.delete_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_delete_dialog_authenticated(self, mock_logged_in, mock_delete):
        """Test POST /chat/delete-dialog/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_delete.return_value = True

        response = self.client.post("/chat/delete-dialog/test-dialog")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
