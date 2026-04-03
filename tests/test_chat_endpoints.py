"""
Tests for chat endpoints (chat page, streaming, models, dialogs, messages)
"""

from pathlib import Path
import pytest
from unittest.mock import patch

from tests.test_base import BaseTestCase, mock_openai_client


class TestChatEndpoints(BaseTestCase):
    """Test chat-related endpoints"""

    def test_configured_models_are_resolved_with_ollama_provider_models(self):
        from chat_client.core.config_utils import resolve_models

        with patch("chat_client.core.config_utils.get_provider_models", return_value=["qwen3:latest", "phi4:latest"]):
            resolved = resolve_models(
                {"gpt-5-nano": "openai"},
                {
                    "openai": {"base_url": "https://api.openai.com/v1", "api_key": "key"},
                    "ollama": {"base_url": "http://localhost:11434/v1", "api_key": "ollama"},
                },
            )

        assert resolved == {
            "gpt-5-nano": "openai",
            "phi4:latest": "ollama",
            "qwen3:latest": "ollama",
        }

    def test_resolve_models_ignores_missing_ollama_provider(self):
        from chat_client.core.config_utils import resolve_models

        with patch("chat_client.core.config_utils.get_provider_models") as mock_get_provider_models:
            resolved = resolve_models({"gpt-5-nano": "openai"}, {"openai": {"base_url": "https://api.openai.com/v1"}})

        assert resolved == {"gpt-5-nano": "openai"}
        mock_get_provider_models.assert_not_called()

    def test_resolve_models_returns_configured_models_when_ollama_lookup_fails(self):
        from chat_client.core.config_utils import resolve_models

        with patch("chat_client.core.config_utils.get_provider_models", side_effect=RuntimeError("offline")):
            resolved = resolve_models(
                {"gpt-5-nano": "openai"},
                {"ollama": {"base_url": "http://localhost:11434/v1", "api_key": "ollama"}},
            )

        assert resolved == {"gpt-5-nano": "openai"}

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

    def test_normalize_chat_messages_with_text_attachment_note(self):
        from chat_client.endpoints.chat_endpoints import _normalize_chat_messages

        messages = [
            {
                "role": "user",
                "content": "Can you see any files?",
                "images": [],
                "attachments": [{"attachment_id": 1, "name": "0059_cipher.txt"}],
            }
        ]

        normalized = _normalize_chat_messages(messages)

        assert len(normalized) == 1
        assert normalized[0]["role"] == "user"
        assert normalized[0]["content"] == (
            "Can you see any files?\n\n"
            "Attached files available to tools:\n"
            "- /mnt/data/0059_cipher.txt"
        )

    def test_build_user_message_text_includes_attachment_note(self):
        from chat_client.core.chat_service import build_user_message_text

        text = build_user_message_text(
            {
                "role": "user",
                "content": "Read this",
                "attachments": [{"attachment_id": 1, "name": "notes.txt"}],
            }
        )

        assert text == "Read this\n\nAttached files available to tools:\n- /mnt/data/notes.txt"

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

    def test_list_local_tools_uses_explicit_local_definitions(self):
        from chat_client.endpoints.chat_endpoints import _list_local_tools

        def get_locale_date_time(locale: str):
            return locale

        local_definitions = [
            {
                "name": "get_locale_date_time",
                "description": "Get local time by locale",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "locale": {"type": "string"},
                    },
                    "required": ["locale"],
                    "additionalProperties": False,
                },
            }
        ]

        with (
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {"get_locale_date_time": get_locale_date_time}),
            patch("chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS", local_definitions),
        ):
            tools = _list_local_tools()

        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "get_locale_date_time"
        assert tools[0]["function"]["description"] == "Get local time by locale"
        assert tools[0]["function"]["parameters"]["required"] == ["locale"]

    def test_list_tools_merges_local_and_mcp_tools(self):
        from chat_client.endpoints.chat_endpoints import _list_tools

        local_tools = [{"type": "function", "function": {"name": "local_tool", "parameters": {"type": "object"}}}]
        mcp_tools = [{"type": "function", "function": {"name": "mcp_tool", "parameters": {"type": "object"}}}]

        with (
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {"local_tool": lambda: "ok"}),
            patch("chat_client.endpoints.chat_endpoints.MCP_SERVER_URL", "http://127.0.0.1:5000/mcp"),
            patch("chat_client.endpoints.chat_endpoints._list_local_tools", return_value=local_tools),
            patch("chat_client.endpoints.chat_endpoints._list_mcp_tools", return_value=mcp_tools),
        ):
            tools = _list_tools()

        assert len(tools) == 2
        assert tools[0]["function"]["name"] == "local_tool"
        assert tools[1]["function"]["name"] == "mcp_tool"

    def test_resolve_tool_models_supports_wildcard(self):
        from chat_client.endpoints.chat_endpoints import _resolve_tool_models

        with (
            patch("chat_client.endpoints.chat_endpoints.MODELS", {"model-a": {}, "model-b": {}}),
            patch("chat_client.endpoints.chat_endpoints.TOOL_MODELS", ["*"]),
        ):
            tool_models = _resolve_tool_models()

        assert tool_models == ["model-a", "model-b"]

    def test_resolve_tool_models_empty_list_disables_tools(self):
        from chat_client.endpoints.chat_endpoints import _resolve_tool_models

        with (
            patch("chat_client.endpoints.chat_endpoints.MODELS", {"model-a": {}, "model-b": {}}),
            patch("chat_client.endpoints.chat_endpoints.TOOL_MODELS", []),
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {"local_tool": lambda: "ok"}),
            patch("chat_client.endpoints.chat_endpoints.MCP_SERVER_URL", "http://127.0.0.1:5000/mcp"),
        ):
            tool_models = _resolve_tool_models()

        assert tool_models == []

    def test_execute_tool_prefers_local_registry_then_falls_back_to_mcp(self):
        from chat_client.endpoints.chat_endpoints import _execute_tool

        local_tool_call = {"function": {"name": "local_tool", "arguments": "{}"}}
        mcp_tool_call = {"function": {"name": "mcp_tool", "arguments": "{}"}}

        with (
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {"local_tool": lambda: "local-result"}),
            patch(
                "chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS",
                [
                    {
                        "name": "local_tool",
                        "description": "Execute local tool",
                        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                    }
                ],
            ),
            patch("chat_client.endpoints.chat_endpoints.MCP_SERVER_URL", "http://127.0.0.1:5000/mcp"),
            patch(
                "chat_client.endpoints.chat_endpoints._list_mcp_tools",
                return_value=[
                    {
                        "type": "function",
                        "function": {
                            "name": "mcp_tool",
                            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                        },
                    }
                ],
            ),
            patch("chat_client.endpoints.chat_endpoints.mcp_client.call_tool", return_value="mcp-result") as mock_mcp_call,
        ):
            local_result = _execute_tool(local_tool_call)
            mcp_result = _execute_tool(mcp_tool_call)

        assert local_result == "local-result"
        assert mcp_result == "mcp-result"
        assert mock_mcp_call.call_count == 1

    def test_attachment_mount_detection_supports_renamed_python_tool(self):
        from chat_client.endpoints.chat_endpoints import _tool_uses_workspace_mount
        from chat_client.tools.python_tool import python_hardened

        with patch(
            "chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS",
            [
                {
                    "name": "some_python_tool",
                    "input_schema": {"type": "object"},
                    "execution": {"mount_workspace": True},
                }
            ],
        ):
            assert _tool_uses_workspace_mount("some_python_tool") is True
            assert _tool_uses_workspace_mount("python_hardened") is False

        with (
            patch("chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS", []),
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {"some_python_tool": python_hardened}),
        ):
            assert _tool_uses_workspace_mount("some_python_tool") is True

    def test_execute_tool_raises_when_no_backend_is_configured(self):
        from chat_client.core import chat_service
        from chat_client.endpoints.chat_endpoints import _execute_tool

        tool_call = {"function": {"name": "python_hardened", "arguments": '{"code":"print(1)"}'}}

        with (
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {}),
            patch("chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS", []),
            patch("chat_client.endpoints.chat_endpoints.MCP_SERVER_URL", ""),
        ):
            with pytest.raises(chat_service.ToolNotConfiguredError) as error:
                _execute_tool(tool_call)

        assert str(error.value) == 'No tool backend is configured for tool "python_hardened".'

    def test_execute_tool_raises_when_tool_does_not_exist(self):
        from chat_client.core import chat_service
        from chat_client.endpoints.chat_endpoints import _execute_tool

        tool_call = {"function": {"name": "missing_tool", "arguments": "{}"}}

        with (
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {"python_hardened": lambda code: code}),
            patch(
                "chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS",
                [
                    {
                        "name": "python_hardened",
                        "description": "Execute Python code",
                        "input_schema": {
                            "type": "object",
                            "properties": {"code": {"type": "string"}},
                            "required": ["code"],
                            "additionalProperties": False,
                        },
                    }
                ],
            ),
            patch("chat_client.endpoints.chat_endpoints.MCP_SERVER_URL", ""),
        ):
            with pytest.raises(chat_service.ToolNotFoundError) as error:
                _execute_tool(tool_call)

        assert str(error.value) == 'Tool "missing_tool" does not exist.'

    def test_execute_tool_raises_for_invalid_json_arguments(self):
        from chat_client.core import chat_service
        from chat_client.endpoints.chat_endpoints import _execute_tool

        tool_call = {"function": {"name": "python_hardened", "arguments": '{"code":"print(1)"'}}

        with (
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {"python_hardened": lambda code: code}),
            patch(
                "chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS",
                [
                    {
                        "name": "python_hardened",
                        "description": "Execute Python code",
                        "input_schema": {
                            "type": "object",
                            "properties": {"code": {"type": "string"}},
                            "required": ["code"],
                            "additionalProperties": False,
                        },
                    }
                ],
            ),
            patch("chat_client.endpoints.chat_endpoints.MCP_SERVER_URL", ""),
        ):
            with pytest.raises(chat_service.ToolArgumentsError) as error:
                _execute_tool(tool_call)

        assert str(error.value) == 'Tool "python_hardened" was called with invalid JSON arguments.'

    def test_execute_tool_raises_for_invalid_argument_shape(self):
        from chat_client.core import chat_service
        from chat_client.endpoints.chat_endpoints import _execute_tool

        tool_call = {"function": {"name": "python_hardened", "arguments": '{"code":1}'}}

        with (
            patch("chat_client.endpoints.chat_endpoints.TOOL_REGISTRY", {"python_hardened": lambda code: code}),
            patch(
                "chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS",
                [
                    {
                        "name": "python_hardened",
                        "description": "Execute Python code",
                        "input_schema": {
                            "type": "object",
                            "properties": {"code": {"type": "string"}},
                            "required": ["code"],
                            "additionalProperties": False,
                        },
                    }
                ],
            ),
            patch("chat_client.endpoints.chat_endpoints.MCP_SERVER_URL", ""),
        ):
            with pytest.raises(chat_service.ToolArgumentsError) as error:
                _execute_tool(tool_call)

        assert str(error.value) == 'Tool "python_hardened" requires argument "code" of type string.'

    def test_execute_tool_raises_backend_error_when_python_runtime_cannot_start(self):
        from chat_client.core import chat_service
        from chat_client.endpoints.chat_endpoints import _execute_tool
        from chat_client.tools.python_runtime import PythonRuntimeError

        tool_call = {"function": {"name": "python_hardened", "arguments": '{"code":"print(1)"}'}}

        with (
            patch(
                "chat_client.endpoints.chat_endpoints.TOOL_REGISTRY",
                {"python_hardened": lambda code: (_ for _ in ()).throw(PythonRuntimeError("missing image"))},
            ),
            patch(
                "chat_client.endpoints.chat_endpoints.LOCAL_TOOL_DEFINITIONS",
                [
                    {
                        "name": "python_hardened",
                        "description": "Execute Python code",
                        "input_schema": {
                            "type": "object",
                            "properties": {"code": {"type": "string"}},
                            "required": ["code"],
                            "additionalProperties": False,
                        },
                    }
                ],
            ),
            patch("chat_client.endpoints.chat_endpoints.MCP_SERVER_URL", ""),
        ):
            with pytest.raises(chat_service.ToolBackendError) as error:
                _execute_tool(tool_call)

        assert str(error.value) == 'Tool "python_hardened" failed: missing image'

    def test_build_model_messages_from_dialog_history_groups_consecutive_tools(self):
        from chat_client.endpoints.chat_endpoints import _build_model_messages_from_dialog_history

        persisted = [
            {"role": "user", "content": "Q", "images": []},
            {
                "role": "tool",
                "content": "R1",
                "tool_call_id": "call_1",
                "tool_name": "t1",
                "arguments_json": '{"x":1}',
            },
            {
                "role": "tool",
                "content": "R2",
                "tool_call_id": "call_2",
                "tool_name": "t2",
                "arguments_json": '{"y":2}',
            },
            {"role": "assistant", "content": "A", "images": []},
        ]

        messages = _build_model_messages_from_dialog_history(persisted)
        assert messages[0] == {"role": "user", "content": "Q", "images": [], "attachments": []}
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == ""
        assert len(messages[1]["tool_calls"]) == 2
        assert messages[2] == {"role": "tool", "tool_call_id": "call_1", "content": "R1"}
        assert messages[3] == {"role": "tool", "tool_call_id": "call_2", "content": "R2"}
        assert messages[4] == {"role": "assistant", "content": "A"}

    def test_build_model_messages_from_assistant_turn_history(self):
        from chat_client.endpoints.chat_endpoints import _build_model_messages_from_dialog_history

        persisted = [
            {"role": "user", "content": "Q", "images": []},
            {
                "role": "assistant_turn",
                "turn_id": "turn-1",
                "events": [
                    {"event_type": "assistant_segment", "reasoning_text": "r1", "content_text": ""},
                    {
                        "event_type": "tool_call",
                        "tool_call_id": "call_1",
                        "tool_name": "python_hardened",
                        "arguments_json": '{"code":"1+1"}',
                        "result_text": "2",
                        "error_text": "",
                    },
                    {"event_type": "assistant_segment", "reasoning_text": "", "content_text": "A"},
                ],
            },
        ]

        messages = _build_model_messages_from_dialog_history(persisted)
        assert messages[0] == {"role": "user", "content": "Q", "images": [], "attachments": []}
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == ""
        assert len(messages[1]["tool_calls"]) == 1
        assert messages[2] == {"role": "tool", "tool_call_id": "call_1", "content": "2"}
        assert messages[3] == {"role": "assistant", "content": "A"}

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
        assert "tool_calls_collapsed_by_default" in data
        assert "system_message_models" in data
        assert "vision_models" in data
        assert "model_capabilities" in data
        assert isinstance(data["model_capabilities"], dict)

    @patch("chat_client.endpoints.chat_endpoints.TOOL_MODELS", ["tool-model"])
    @patch("chat_client.endpoints.chat_endpoints.VISION_MODELS", ["vision-model"])
    @patch(
        "chat_client.endpoints.chat_endpoints.MODELS",
        {"vision-model": {"provider": "x"}, "tool-model": {"provider": "x"}, "combo-model": {"provider": "x"}},
    )
    def test_config_endpoint_includes_model_capabilities(self):
        response = self.client.get("/config")

        assert response.status_code == 200
        data = response.json()
        assert data["model_capabilities"] == {
            "vision-model": {
                "supports_images": True,
                "supports_tools": False,
                "supports_attachments": False,
                "supports_thinking": False,
            },
            "tool-model": {
                "supports_images": False,
                "supports_tools": True,
                "supports_attachments": True,
                "supports_thinking": False,
            },
            "combo-model": {
                "supports_images": False,
                "supports_tools": False,
                "supports_attachments": False,
                "supports_thinking": False,
            },
        }

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

    @patch("chat_client.repositories.chat_repository.get_messages")
    @patch("chat_client.repositories.chat_repository.get_dialog")
    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_uses_persisted_tool_history_for_dialog(
        self,
        mock_logged_in,
        mock_openai_class,
        mock_get_dialog,
        mock_get_messages,
    ):
        mock_logged_in.return_value = 1
        mock_get_dialog.return_value = {"dialog_id": "dlg1", "title": "x", "created": "2026-01-01T00:00:00"}
        mock_get_messages.return_value = [
            {"role": "user", "content": "Find article", "images": []},
            {"role": "assistant", "content": "", "images": []},
            {
                "role": "tool",
                "content": "Article JSON",
                "tool_call_id": "call_1",
                "tool_name": "get_wikipedia_pages_json",
                "arguments_json": '{"title":"X"}',
                "images": [],
            },
            {"role": "assistant", "content": "I found it", "images": []},
            {"role": "user", "content": "Summarize it", "images": []},
        ]

        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client

        response = self.client.post(
            "/chat",
            json={
                "dialog_id": "dlg1",
                "messages": [{"role": "user", "content": "client payload should not override db"}],
                "model": "test-model",
            },
        )

        assert response.status_code == 200
        _ = response.content
        called_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert called_messages[0]["content"] == "Find article"
        assert any(msg.get("role") == "assistant" and msg.get("tool_calls") for msg in called_messages)
        assert any(msg.get("role") == "tool" and msg.get("tool_call_id") == "call_1" for msg in called_messages)

    @patch("chat_client.repositories.chat_repository.get_messages")
    @patch("chat_client.repositories.chat_repository.get_dialog")
    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_passes_all_user_assistant_tool_messages_to_model(
        self,
        mock_logged_in,
        mock_openai_class,
        mock_get_dialog,
        mock_get_messages,
    ):
        mock_logged_in.return_value = 1
        mock_get_dialog.return_value = {"dialog_id": "dlg2", "title": "x", "created": "2026-01-01T00:00:00"}
        mock_get_messages.return_value = [
            {"role": "user", "content": "U1", "images": []},
            {"role": "assistant", "content": "A1", "images": []},
            {
                "role": "tool",
                "content": "T1",
                "tool_call_id": "call_1",
                "tool_name": "tool_one",
                "arguments_json": "{}",
                "images": [],
            },
            {"role": "assistant", "content": "A2", "images": []},
            {"role": "user", "content": "U2", "images": []},
            {
                "role": "tool",
                "content": "T2",
                "tool_call_id": "call_2",
                "tool_name": "tool_two",
                "arguments_json": "{}",
                "images": [],
            },
        ]

        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client

        response = self.client.post(
            "/chat",
            json={
                "dialog_id": "dlg2",
                "messages": [{"role": "user", "content": "payload ignored for persisted dialog history"}],
                "model": "test-model",
            },
        )

        assert response.status_code == 200
        _ = response.content
        called_messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        assert called_messages == [
            {"role": "user", "content": "U1", "images": [], "attachments": []},
            {"role": "assistant", "content": "A1", "images": []},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "tool_one", "arguments": "{}"},
                    }
                ],
                "images": [],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "T1", "images": []},
            {"role": "assistant", "content": "A2", "images": []},
            {"role": "user", "content": "U2", "images": [], "attachments": []},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "tool_two", "arguments": "{}"},
                    }
                ],
                "images": [],
            },
            {"role": "tool", "tool_call_id": "call_2", "content": "T2", "images": []},
        ]

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
    @patch("chat_client.endpoints.chat_endpoints.TOOL_MODELS", ["test-model"])
    @patch("chat_client.endpoints.chat_endpoints.MODELS", {"test-model": {"provider": "x"}})
    @patch("chat_client.repositories.attachment_repository.get_attachments")
    @patch("chat_client.repositories.chat_repository.create_message")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_message_authenticated(self, mock_logged_in, mock_create, mock_get_attachments):
        """Test POST /chat/create-message/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_create.return_value = 123  # message_id
        mock_get_attachments.return_value = [
            {
                "attachment_id": 7,
                "name": "notes.txt",
                "content_type": "text/plain",
                "size_bytes": 5,
                "storage_path": "/tmp/notes.txt",
            }
        ]

        response = self.client.post(
            "/chat/create-message/test-dialog",
            json={
                "content": "Test message",
                "role": "user",
                "model": "test-model",
                "images": [{"data_url": "data:image/png;base64,AAAA"}],
                "attachments": [{"attachment_id": 7, "name": "notes.txt", "content_type": "text/plain", "size_bytes": 5}],
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
            [{"attachment_id": 7, "name": "notes.txt", "content_type": "text/plain", "size_bytes": 5}],
        )
        mock_get_attachments.assert_called_once_with(1, [7])

    @patch("chat_client.endpoints.chat_endpoints.TOOL_MODELS", ["test-model"])
    @patch("chat_client.endpoints.chat_endpoints.MODELS", {"test-model": {"provider": "x"}})
    @patch("chat_client.repositories.attachment_repository.get_attachments")
    @patch("chat_client.repositories.chat_repository.create_message")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_message_validates_attachments(self, mock_logged_in, mock_create, mock_get_attachments):
        mock_logged_in.return_value = 1
        mock_create.return_value = 123
        mock_get_attachments.return_value = [
            {
                "attachment_id": 7,
                "name": "notes.txt",
                "content_type": "text/plain",
                "size_bytes": 5,
                "storage_path": "/tmp/notes.txt",
            }
        ]

        response = self.client.post(
            "/chat/create-message/test-dialog",
            json={
                "content": "Use attached file",
                "role": "user",
                "model": "test-model",
                "attachments": [{"attachment_id": 7, "name": "notes.txt", "content_type": "text/plain", "size_bytes": 5}],
            },
        )

        assert response.status_code == 200
        mock_get_attachments.assert_called_once_with(1, [7])

    @patch("chat_client.core.user_session.is_logged_in")
    def test_upload_attachment_not_authenticated(self, mock_logged_in):
        mock_logged_in.return_value = False

        response = self.client.post(
            "/chat/upload-attachment",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

        assert response.status_code == 401

    @patch("chat_client.repositories.attachment_repository.get_attachment")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_preview_attachment_serves_html_as_plain_text(self, mock_logged_in, mock_get_attachment, tmp_path):
        mock_logged_in.return_value = 1
        html_path = tmp_path / "sample.html"
        html_path.write_text("<h1>Hello</h1>", encoding="utf-8")
        mock_get_attachment.return_value = {
            "attachment_id": 7,
            "name": "sample.html",
            "content_type": "text/html",
            "size_bytes": 14,
            "storage_path": str(html_path),
        }

        response = self.client.get("/chat/attachment/7/preview")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "<h1>Hello</h1>" in response.text

    @patch("chat_client.repositories.attachment_repository.get_attachment")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_preview_attachment_serves_images_inline(self, mock_logged_in, mock_get_attachment, tmp_path):
        mock_logged_in.return_value = 1
        image_path = tmp_path / "sample.png"
        image_path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
            b"\x90wS\xde"
            b"\x00\x00\x00\x0cIDAT\x08\x99c```\x00\x00\x00\x04\x00\x01"
            b"\xf6\x178U"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        mock_get_attachment.return_value = {
            "attachment_id": 8,
            "name": "sample.png",
            "content_type": "image/png",
            "size_bytes": image_path.stat().st_size,
            "storage_path": str(image_path),
        }

        response = self.client.get("/chat/attachment/8/preview")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert response.headers["content-disposition"].startswith("inline;")

    @patch("chat_client.endpoints.chat_endpoints.attachment_service.build_attachment_storage_path")
    @patch("chat_client.repositories.attachment_repository.get_attachment")
    @patch("chat_client.repositories.attachment_repository.update_attachment_storage_path")
    @patch("chat_client.repositories.attachment_repository.create_attachment")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_upload_attachment_authenticated(
        self,
        mock_logged_in,
        mock_create_attachment,
        mock_update_attachment_storage_path,
        mock_get_attachment,
        mock_build_attachment_storage_path,
    ):
        mock_logged_in.return_value = 1
        mock_create_attachment.return_value = 42
        upload_path = Path("tests/.test-data/uploaded_notes.txt")
        mock_build_attachment_storage_path.return_value = upload_path
        mock_get_attachment.return_value = {
            "attachment_id": 42,
            "name": "notes.txt",
            "content_type": "text/plain",
            "size_bytes": 5,
            "storage_path": str(upload_path),
        }

        response = self.client.post(
            "/chat/upload-attachment",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["attachment_id"] > 0
        assert data["name"] == "notes.txt"
        assert data["content_type"] == "text/plain"
        assert data["size_bytes"] == 5
        assert upload_path.read_bytes() == b"hello"

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

    @patch("chat_client.endpoints.chat_endpoints.TOOL_MODELS", [])
    @patch("chat_client.endpoints.chat_endpoints.MODELS", {"test-model": {"provider": "x"}})
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_message_rejects_attachments_for_model_without_attachment_support(self, mock_logged_in):
        mock_logged_in.return_value = 1

        response = self.client.post(
            "/chat/create-message/test-dialog",
            json={
                "content": "Use attached file",
                "role": "user",
                "model": "test-model",
                "attachments": [{"attachment_id": 7, "name": "notes.txt", "content_type": "text/plain", "size_bytes": 5}],
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert "does not support file attachments" in data["message"]

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
