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
        assert normalized[0]["content"] == ("Can you see any files?\n\nAttached files available to tools:\n- /mnt/data/0059_cipher.txt")

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

    def test_generate_dialog_title_normalizes_provider_response(self):
        from chat_client.endpoints.chat_endpoints import _generate_dialog_title

        mock_response = type(
            "Response",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type("Message", (), {"content": '  "Summarized title"  '})(),
                        },
                    )()
                ]
            },
        )()

        mock_client = type(
            "Client",
            (),
            {
                "chat": type(
                    "Chat",
                    (),
                    {
                        "completions": type(
                            "Completions",
                            (),
                            {"create": lambda self, **kwargs: mock_response},
                        )()
                    },
                )()
            },
        )()

        with (
            patch("chat_client.endpoints.chat_endpoints._resolve_provider_info", return_value={"api_key": "key", "base_url": "http://x"}),
            patch("chat_client.endpoints.chat_endpoints.OpenAI", return_value=mock_client),
        ):
            title = _generate_dialog_title(
                "How do I mount a network drive on Linux?",
                "test-model",
            )

        assert title == "Summarized title"

    def test_generate_dialog_title_uses_fixed_placeholder_when_provider_returns_no_choices(self):
        from chat_client.endpoints.chat_endpoints import _generate_dialog_title

        mock_response = type("Response", (), {"choices": []})()

        mock_client = type(
            "Client",
            (),
            {
                "chat": type(
                    "Chat",
                    (),
                    {
                        "completions": type(
                            "Completions",
                            (),
                            {"create": lambda self, **kwargs: mock_response},
                        )()
                    },
                )()
            },
        )()

        with (
            patch("chat_client.endpoints.chat_endpoints._resolve_provider_info", return_value={"api_key": "key", "base_url": "http://x"}),
            patch("chat_client.endpoints.chat_endpoints.OpenAI", return_value=mock_client),
        ):
            title = _generate_dialog_title(
                "Summarize release notes for version 2.1",
                "test-model",
            )

        assert title == "Summarize release notes for version 2 1"

    def test_derive_dialog_title_from_user_message_strips_markup_and_symbols(self):
        from chat_client.endpoints.chat_endpoints import _derive_dialog_title_from_user_message

        title = _derive_dialog_title_from_user_message(
            "<p>By listing the first six prime numbers: $2, 3, 5, 7, 11$, and $13$, we can see</p>"
        )

        assert title == "By listing the first six prime numbers 2 3 5 7 11 and 13 we can see"

    def test_extract_first_user_message_uses_first_user_message(self):
        from chat_client.endpoints.chat_endpoints import _extract_first_user_message

        first_user_message = _extract_first_user_message(
            [
                {"role": "user", "content": "How do I mount a network drive?", "images": [], "attachments": []},
                {
                    "role": "assistant_turn",
                    "events": [
                        {"event_type": "assistant_segment", "reasoning_text": "thinking", "content_text": ""},
                        {"event_type": "assistant_segment", "reasoning_text": "", "content_text": "Use mount -t cifs ..."},
                    ],
                },
                {"role": "user", "content": "Thanks", "images": [], "attachments": []},
            ]
        )

        assert first_user_message == "How do I mount a network drive?"

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
        """Test GET /api/chat/config"""
        response = self.client.get("/api/chat/config")
        assert response.status_code == 200
        data = response.json()
        assert "default_model" in data
        assert "use_katex" in data
        assert "system_message_denylist" in data
        assert "vision_models" in data
        assert "model_capabilities" in data
        assert "model_providers" in data
        assert isinstance(data["model_capabilities"], dict)

    @patch("chat_client.endpoints.chat_endpoints.TOOL_MODELS", ["tool-model"])
    @patch("chat_client.endpoints.chat_endpoints.VISION_MODELS", ["vision-model"])
    @patch(
        "chat_client.endpoints.chat_endpoints.MODELS",
        {"vision-model": {"provider": "x"}, "tool-model": {"provider": "x"}, "combo-model": {"provider": "x"}},
    )
    def test_config_endpoint_includes_model_capabilities(self):
        response = self.client.get("/api/chat/config")

        assert response.status_code == 200
        data = response.json()
        assert data["model_capabilities"] == {
            "vision-model": {
                "supports_images": True,
                "supports_tools": False,
                "supports_attachments": False,
                "supports_reasoning": False,
                "supports_thinking": False,
                "supports_thinking_control": False,
                "supports_system_messages": True,
                "context_length": None,
            },
            "tool-model": {
                "supports_images": False,
                "supports_tools": True,
                "supports_attachments": True,
                "supports_reasoning": False,
                "supports_thinking": False,
                "supports_thinking_control": False,
                "supports_system_messages": True,
                "context_length": None,
            },
            "combo-model": {
                "supports_images": False,
                "supports_tools": False,
                "supports_attachments": False,
                "supports_reasoning": False,
                "supports_thinking": False,
                "supports_thinking_control": False,
                "supports_system_messages": True,
                "context_length": None,
            },
        }
        assert data["model_providers"] == {
            "vision-model": "x",
            "tool-model": "x",
            "combo-model": "x",
        }

    @patch(
        "chat_client.endpoints.chat_endpoints.MODELS",
        {"gpt-5": "openai", "qwen3:latest": "ollama"},
    )
    def test_build_model_providers(self):
        from chat_client.endpoints.chat_endpoints import _build_model_providers

        assert _build_model_providers() == {
            "gpt-5": "openai",
            "qwen3:latest": "ollama",
        }

    def test_list_models(self):
        """Test GET /api/chat/models (available models)"""
        with (
            patch("chat_client.endpoints.chat_endpoints.MODELS", {"qwen3:latest": "ollama", "gpt-5-nano": "openai"}),
            patch(
                "chat_client.endpoints.chat_endpoints.get_ollama_model_metadata",
                return_value={"context_length": 32768, "supports_images": False, "supports_tools": True, "supports_thinking": False},
            ),
        ):
            response = self.client.get("/api/chat/models")
        assert response.status_code == 200
        data = response.json()
        assert "model_names" in data
        assert isinstance(data["model_names"], list)
        assert data["model_names"] == ["qwen3:latest", "gpt-5-nano"]
        assert data["models"] == [
            {"name": "qwen3:latest", "context_length": 32768},
            {"name": "gpt-5-nano"},
        ]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_not_authenticated(self, mock_logged_in):
        """Test POST /chat when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "test-model",
                "dialog_id": "077fc48f-9954-4eaf-942e-2a734770cc3b",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "must be logged in" in data["message"]
        assert data["redirect"] == "/user/login?next=/chat/077fc48f-9954-4eaf-942e-2a734770cc3b&reason=auth_required"

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
    @patch("chat_client.endpoints.chat_endpoints.MODELS", {"test-model": "openai"})
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

    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.endpoints.chat_endpoints.MODELS", {"test-model": "openai"})
    @patch(
        "chat_client.endpoints.chat_endpoints._supports_model_thinking_control",
        return_value=True,
    )
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_passes_reasoning_effort_for_openai(
        self,
        mock_logged_in,
        _mock_supports_model_thinking_control,
        mock_openai_class,
    ):
        mock_logged_in.return_value = 1

        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client

        response = self.client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "test-model",
                "reasoning_effort": "medium",
            },
        )

        assert response.status_code == 200
        _ = response.content
        assert mock_client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "medium"

    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.endpoints.chat_endpoints.MODELS", {"test-model": "ollama"})
    @patch(
        "chat_client.endpoints.chat_endpoints._supports_model_thinking_control",
        return_value=True,
    )
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_passes_reasoning_effort_for_thinking_capable_ollama(
        self,
        mock_logged_in,
        _mock_supports_model_thinking_control,
        mock_openai_class,
    ):
        mock_logged_in.return_value = 1

        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client

        response = self.client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "test-model",
                "reasoning_effort": "high",
            },
        )

        assert response.status_code == 200
        _ = response.content
        assert mock_client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "high"

    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.endpoints.chat_endpoints.MODELS", {"test-model": "ollama"})
    @patch(
        "chat_client.endpoints.chat_endpoints._supports_model_thinking_control",
        return_value=True,
    )
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_passes_none_reasoning_effort_for_ollama(
        self,
        mock_logged_in,
        _mock_supports_model_thinking_control,
        mock_openai_class,
    ):
        mock_logged_in.return_value = 1

        mock_client = mock_openai_client()
        mock_openai_class.return_value = mock_client

        response = self.client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "test-model",
                "reasoning_effort": "none",
            },
        )

        assert response.status_code == 200
        _ = response.content
        assert mock_client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "none"

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

    @patch("chat_client.endpoints.chat_endpoints._supports_model_images", return_value=True)
    @patch("chat_client.endpoints.chat_endpoints.VISION_MODELS", [])
    @patch("chat_client.endpoints.chat_endpoints.OpenAI")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_chat_response_stream_with_images_uses_dynamic_model_capabilities(
        self,
        mock_logged_in,
        mock_openai_class,
        _mock_supports_model_images,
    ):
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
        """Test POST /api/chat/dialogs when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/api/chat/dialogs", json={"title": "Test Dialog"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert "must be logged in" in data["message"]
        assert data["redirect"] == "/user/login?reason=auth_required"

    @patch("chat_client.repositories.chat_repository.create_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_dialog_authenticated(self, mock_logged_in, mock_create):
        """Test POST /api/chat/dialogs when authenticated"""
        mock_logged_in.return_value = 1
        mock_create.return_value = "test-dialog-id"

        response = self.client.post("/api/chat/dialogs", json={"title": "Test Dialog"})

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["dialog_id"] == "test-dialog-id"
        mock_create.assert_called_once_with(1, "Test Dialog")

    @patch("chat_client.repositories.chat_repository.create_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_dialog_derives_title_from_initial_message_when_placeholder_is_used(self, mock_logged_in, mock_create):
        mock_logged_in.return_value = 1
        mock_create.return_value = "test-dialog-id"

        response = self.client.post(
            "/api/chat/dialogs",
            json={
                "title": "New Chat",
                "initial_message": "Summarize release notes for version 2.1",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["dialog_id"] == "test-dialog-id"
        mock_create.assert_called_once_with(1, "Summarize release notes for version 2 1")

    @patch("chat_client.repositories.chat_repository.create_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_dialog_validation_error(self, mock_logged_in, mock_create):
        """Test POST /api/chat/dialogs with validation error"""
        mock_logged_in.return_value = 1
        from chat_client.core.exceptions_validation import UserValidate

        mock_create.side_effect = UserValidate("Invalid title")

        response = self.client.post("/api/chat/dialogs", json={"title": ""})

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert "Invalid title" in data["message"]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_message_not_authenticated(self, mock_logged_in):
        """Test POST /api/chat/dialogs/{dialog_id}/messages when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/api/chat/dialogs/test-dialog/messages", json={"content": "Test message", "role": "user"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/chat/test-dialog&reason=auth_required"

    @patch("chat_client.endpoints.chat_endpoints.VISION_MODELS", ["test-model"])
    @patch("chat_client.endpoints.chat_endpoints.TOOL_MODELS", ["test-model"])
    @patch("chat_client.endpoints.chat_endpoints.MODELS", {"test-model": {"provider": "x"}})
    @patch("chat_client.repositories.attachment_repository.get_attachments")
    @patch("chat_client.repositories.chat_repository.create_message")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_message_authenticated(self, mock_logged_in, mock_create, mock_get_attachments):
        """Test POST /api/chat/dialogs/{dialog_id}/messages when authenticated"""
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
            "/api/chat/dialogs/test-dialog/messages",
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
            "/api/chat/dialogs/test-dialog/messages",
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
    def test_generate_dialog_title_not_authenticated(self, mock_logged_in):
        mock_logged_in.return_value = False

        response = self.client.post(
            "/api/chat/dialogs/test-dialog/title",
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/chat/test-dialog&reason=auth_required"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_create_assistant_turn_events_not_authenticated(self, mock_logged_in):
        mock_logged_in.return_value = False

        response = self.client.post(
            "/api/chat/dialogs/test-dialog/assistant-turn-events",
            json={"turn_id": "turn-1", "events": []},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/chat/test-dialog&reason=auth_required"

    @patch("chat_client.endpoints.chat_endpoints.DIALOG_TITLE_MODEL", "title-model")
    @patch("chat_client.repositories.chat_repository.update_dialog_title")
    @patch("chat_client.repositories.chat_repository.get_messages")
    @patch("chat_client.repositories.chat_repository.get_dialog")
    @patch("chat_client.endpoints.chat_endpoints._generate_dialog_title")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_generate_dialog_title_authenticated(
        self,
        mock_logged_in,
        mock_generate_dialog_title,
        mock_get_dialog,
        mock_get_messages,
        mock_update_dialog_title,
    ):
        mock_logged_in.return_value = 1
        mock_get_dialog.return_value = {"dialog_id": "test-dialog", "title": "New Chat", "created": "2026-01-01T00:00:00"}
        mock_get_messages.return_value = [
            {"role": "user", "content": "How do I mount a network drive on Linux?", "images": [], "attachments": []},
            {
                "role": "assistant_turn",
                "events": [
                    {"event_type": "assistant_segment", "reasoning_text": "", "content_text": "Use mount -t cifs ..."},
                ],
            },
        ]
        mock_generate_dialog_title.return_value = "Mounted network drive"
        mock_update_dialog_title.return_value = {"dialog_id": "test-dialog", "title": "Mounted network drive"}

        response = self.client.post(
            "/api/chat/dialogs/test-dialog/title",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["title"] == "Mounted network drive"
        assert data["generated"] is True
        mock_generate_dialog_title.assert_called_once_with(
            "How do I mount a network drive on Linux?",
            "title-model",
            1,
            "test-dialog",
        )
        mock_update_dialog_title.assert_called_once_with(1, "test-dialog", "Mounted network drive")

    @patch("chat_client.endpoints.chat_endpoints.DIALOG_TITLE_MODEL", "")
    @patch("chat_client.repositories.chat_repository.update_dialog_title")
    @patch("chat_client.repositories.chat_repository.get_messages")
    @patch("chat_client.repositories.chat_repository.get_dialog")
    @patch("chat_client.endpoints.chat_endpoints._generate_dialog_title")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_generate_dialog_title_uses_user_message_fallback_when_no_title_model_is_configured(
        self,
        mock_logged_in,
        mock_generate_dialog_title,
        mock_get_dialog,
        mock_get_messages,
        mock_update_dialog_title,
    ):
        mock_logged_in.return_value = 1
        mock_get_dialog.return_value = {"dialog_id": "test-dialog", "title": "New Chat", "created": "2026-01-01T00:00:00"}
        mock_get_messages.return_value = [
            {"role": "user", "content": "<p>How do I mount a network drive on Linux?</p>", "images": [], "attachments": []},
        ]
        mock_update_dialog_title.return_value = {"dialog_id": "test-dialog", "title": "How do I mount a network drive on Linux"}

        response = self.client.post(
            "/api/chat/dialogs/test-dialog/title",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["title"] == "How do I mount a network drive on Linux"
        assert data["generated"] is True
        mock_generate_dialog_title.assert_not_called()
        mock_update_dialog_title.assert_called_once_with(1, "test-dialog", "How do I mount a network drive on Linux")

    @patch("chat_client.repositories.chat_repository.update_dialog_title")
    @patch("chat_client.repositories.chat_repository.get_messages")
    @patch("chat_client.repositories.chat_repository.get_dialog")
    @patch("chat_client.endpoints.chat_endpoints._generate_dialog_title")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_generate_dialog_title_skips_when_dialog_already_named(
        self,
        mock_logged_in,
        mock_generate_dialog_title,
        mock_get_dialog,
        mock_get_messages,
        mock_update_dialog_title,
    ):
        mock_logged_in.return_value = 1
        mock_get_dialog.return_value = {"dialog_id": "test-dialog", "title": "Mounted network drive", "created": "2026-01-01T00:00:00"}
        mock_get_messages.return_value = []

        response = self.client.post(
            "/api/chat/dialogs/test-dialog/title",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["generated"] is False
        assert data["title"] == "Mounted network drive"
        mock_generate_dialog_title.assert_not_called()
        mock_update_dialog_title.assert_not_called()

    @patch("chat_client.core.user_session.is_logged_in")
    def test_upload_attachment_not_authenticated(self, mock_logged_in):
        mock_logged_in.return_value = False

        response = self.client.post(
            "/api/chat/attachments",
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

        response = self.client.get("/api/chat/attachments/7/preview")

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

        response = self.client.get("/api/chat/attachments/8/preview")

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
            "/api/chat/attachments",
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
        """Test POST /api/chat/dialogs/{dialog_id}/messages rejects images for non-vision model"""
        mock_logged_in.return_value = 1

        response = self.client.post(
            "/api/chat/dialogs/test-dialog/messages",
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
            "/api/chat/dialogs/test-dialog/messages",
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
        """Test GET /api/chat/dialogs/{dialog_id} when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/api/chat/dialogs/test-dialog")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/chat/test-dialog&reason=auth_required"

    @patch("chat_client.repositories.chat_repository.get_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_dialog_authenticated(self, mock_logged_in, mock_get):
        """Test GET /api/chat/dialogs/{dialog_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_get.return_value = {"dialog_id": "test-dialog", "title": "Test Dialog", "user_id": 1}

        response = self.client.get("/api/chat/dialogs/test-dialog")

        assert response.status_code == 200
        data = response.json()
        assert data["dialog_id"] == "test-dialog"
        assert data["title"] == "Test Dialog"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_messages_not_authenticated(self, mock_logged_in):
        """Test GET /api/chat/dialogs/{dialog_id}/messages when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.get("/api/chat/dialogs/test-dialog/messages")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/chat/test-dialog&reason=auth_required"

    @patch("chat_client.repositories.chat_repository.get_messages")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_messages_authenticated(self, mock_logged_in, mock_get):
        """Test GET /api/chat/dialogs/{dialog_id}/messages when authenticated"""
        mock_logged_in.return_value = 1
        mock_get.return_value = [{"message_id": 1, "content": "Hello", "role": "user", "dialog_id": "test-dialog"}]

        response = self.client.get("/api/chat/dialogs/test-dialog/messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Hello"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_dialog_usage_not_authenticated(self, mock_logged_in):
        mock_logged_in.return_value = False

        response = self.client.get("/api/chat/dialogs/test-dialog/usage")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/chat/test-dialog&reason=auth_required"

    @patch("chat_client.repositories.chat_repository.list_dialog_usage_events")
    @patch("chat_client.repositories.chat_repository.get_dialog_usage_by_turn")
    @patch("chat_client.repositories.chat_repository.get_dialog_usage_totals")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_dialog_usage_authenticated(
        self,
        mock_logged_in,
        mock_get_totals,
        mock_get_turns,
        mock_list_events,
    ):
        mock_logged_in.return_value = 1
        mock_get_totals.return_value = {
            "request_count": 2,
            "input_tokens": 1700,
            "cached_input_tokens": 1000,
            "output_tokens": 65,
            "total_tokens": 1765,
            "reasoning_tokens": 7,
            "currency": "USD",
            "cost_amount": "0.00151250",
        }
        mock_get_turns.return_value = [
            {
                "turn_id": "turn-server-1",
                "models": ["gpt-5"],
                "request_count": 2,
                "input_tokens": 1700,
                "cached_input_tokens": 1000,
                "output_tokens": 65,
                "total_tokens": 1765,
                "reasoning_tokens": 7,
                "currency": "USD",
                "cost_amount": "0.00151250",
                "first_created": "2026-01-01T00:00:01",
            }
        ]
        mock_list_events.return_value = [
            {
                "turn_id": "turn-server-1",
                "round_index": 1,
                "provider": "openai",
                "model": "gpt-5",
                "call_type": "chat",
                "request_id": "cmpl-1",
                "input_tokens": 1200,
                "cached_input_tokens": 1000,
                "output_tokens": 45,
                "total_tokens": 1245,
                "reasoning_tokens": 7,
                "currency": "USD",
                "cost_amount": "0.00068750",
                "usage_source": "provider",
                "created": "2026-01-01T00:00:01",
            }
        ]

        response = self.client.get("/api/chat/dialogs/test-dialog/usage")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["dialog_id"] == "test-dialog"
        assert data["totals"]["cached_input_tokens"] == 1000
        assert data["turns"][0]["turn_id"] == "turn-server-1"
        assert data["events"][0]["request_id"] == "cmpl-1"

    @patch("chat_client.repositories.chat_repository.list_dialog_usage_events")
    @patch("chat_client.repositories.chat_repository.get_dialog_usage_by_turn")
    @patch("chat_client.repositories.chat_repository.get_dialog_usage_totals")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_dialog_usage_preserved_after_dialog_delete(
        self,
        mock_logged_in,
        mock_get_totals,
        mock_get_turns,
        mock_list_events,
    ):
        mock_logged_in.return_value = 1
        mock_get_totals.return_value = {
            "request_count": 1,
            "input_tokens": 1200,
            "cached_input_tokens": 800,
            "output_tokens": 45,
            "total_tokens": 1245,
            "reasoning_tokens": 7,
            "currency": "USD",
            "cost_amount": "0.00068750",
        }
        mock_get_turns.return_value = [
            {
                "turn_id": "turn-server-1",
                "models": ["gpt-5"],
                "request_count": 1,
                "input_tokens": 1200,
                "cached_input_tokens": 800,
                "output_tokens": 45,
                "total_tokens": 1245,
                "reasoning_tokens": 7,
                "currency": "USD",
                "cost_amount": "0.00068750",
                "first_created": "2026-01-01T00:00:01",
            }
        ]
        mock_list_events.return_value = [
            {
                "turn_id": "turn-server-1",
                "dialog_title": "Deleted dialog",
                "round_index": 1,
                "provider": "openai",
                "model": "gpt-5",
                "call_type": "chat",
                "request_id": "cmpl-1",
                "input_tokens": 1200,
                "cached_input_tokens": 800,
                "output_tokens": 45,
                "total_tokens": 1245,
                "reasoning_tokens": 7,
                "currency": "USD",
                "cost_amount": "0.00068750",
                "usage_source": "provider",
                "created": "2026-01-01T00:00:01",
            }
        ]

        response = self.client.get("/api/chat/dialogs/deleted-dialog/usage")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["dialog_id"] == "deleted-dialog"
        assert data["events"][0]["dialog_title"] == "Deleted dialog"

    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_user_usage_not_authenticated(self, mock_logged_in):
        mock_logged_in.return_value = False

        response = self.client.get("/api/user/usage")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True

    @patch("chat_client.repositories.chat_repository.get_user_usage_by_dialog_info")
    @patch("chat_client.repositories.chat_repository.get_user_usage_totals")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_user_usage_authenticated(self, mock_logged_in, mock_get_totals, mock_get_usage_info):
        mock_logged_in.return_value = 1
        mock_get_totals.return_value = {
            "request_count": 2,
            "input_tokens": 1700,
            "cached_input_tokens": 1000,
            "output_tokens": 65,
            "total_tokens": 1765,
            "reasoning_tokens": 7,
            "currency": "USD",
            "cost_amount": "0.00151250",
        }
        mock_get_usage_info.return_value = {
            "dialogs": [
                {
                    "dialog_id": "dialog-1",
                    "title": "Recent dialog",
                    "request_count": 2,
                    "input_tokens": 1700,
                    "cached_input_tokens": 1000,
                    "output_tokens": 65,
                    "total_tokens": 1765,
                    "reasoning_tokens": 7,
                    "currency": "USD",
                    "cost_amount": "0.00151250",
                    "first_created": "2026-01-01T00:00:01",
                    "last_created": "2026-01-01T00:00:02",
                }
            ],
            "has_next": False,
        }

        response = self.client.get("/api/user/usage")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["totals"]["cost_amount"] == "0.00151250"
        assert data["dialogs_info"]["dialogs"][0]["dialog_id"] == "dialog-1"
        assert data["dialogs"][0]["dialog_id"] == "dialog-1"
        mock_get_usage_info.assert_called_once_with(1, current_page=1)

    @patch("chat_client.repositories.chat_repository.get_user_usage_totals")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_usage_page_authenticated(self, mock_logged_in, mock_get_totals):
        mock_logged_in.return_value = 1
        mock_get_totals.return_value = {
            "request_count": 2,
            "input_tokens": 1700,
            "cached_input_tokens": 1000,
            "output_tokens": 65,
            "total_tokens": 1765,
            "reasoning_tokens": 7,
            "currency": "USD",
            "cost_amount": "0.00151250",
        }

        response = self.client.get("/user/usage")

        assert response.status_code == 200
        assert "Usage" in response.text
        assert "0.00151250 USD" in response.text
        assert "Usage by dialog" in response.text
        assert "load-more-usage-dialogs" in response.text
        assert "usage-dialogs-container" in response.text

    @patch("chat_client.core.user_session.is_logged_in")
    def test_get_user_usage_invalid_page(self, mock_logged_in):
        mock_logged_in.return_value = 1

        response = self.client.get("/api/user/usage?page=abc")

        assert response.status_code == 400
        data = response.json()
        assert data["error"] is True
        assert "Invalid page parameter" in data["message"]

    @patch("chat_client.core.user_session.is_logged_in")
    def test_update_message_not_authenticated(self, mock_logged_in):
        """Test POST /chat/messages/{message_id} when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/api/chat/messages/1?next=/chat/test-dialog", json={"content": "Updated message"})

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/chat/test-dialog&reason=auth_required"

    @patch("chat_client.repositories.chat_repository.update_message")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_update_message_authenticated(self, mock_logged_in, mock_update):
        """Test POST /chat/messages/{message_id} when authenticated"""
        mock_logged_in.return_value = 1
        mock_update.return_value = {"message_id": 1}

        response = self.client.post("/api/chat/messages/1", json={"content": "Updated message"})

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["message_id"] == 1

    @patch("chat_client.repositories.chat_repository.update_dialog_title")
    @patch("chat_client.endpoints.chat_endpoints._derive_dialog_title_from_user_message")
    @patch("chat_client.repositories.chat_repository.update_message")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_update_message_updates_dialog_title_when_first_user_message_is_edited(
        self,
        mock_logged_in,
        mock_update_message,
        mock_derive_dialog_title,
        mock_update_dialog_title,
    ):
        mock_logged_in.return_value = 1
        mock_update_message.return_value = {
            "message_id": 1,
            "dialog_id": "test-dialog",
            "was_first_user_message": True,
        }
        mock_derive_dialog_title.return_value = "Updated topic"
        mock_update_dialog_title.return_value = {"dialog_id": "test-dialog", "title": "Updated topic"}

        response = self.client.post("/api/chat/messages/1", json={"content": "Updated first message"})

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert data["dialog_title"] == "Updated topic"
        mock_derive_dialog_title.assert_called_once_with("Updated first message")
        mock_update_dialog_title.assert_called_once_with(1, "test-dialog", "Updated topic")

    @patch("chat_client.repositories.chat_repository.update_dialog_title")
    @patch("chat_client.endpoints.chat_endpoints._derive_dialog_title_from_user_message")
    @patch("chat_client.repositories.chat_repository.update_message")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_update_message_does_not_update_dialog_title_when_message_is_not_first_user_message(
        self,
        mock_logged_in,
        mock_update_message,
        mock_derive_dialog_title,
        mock_update_dialog_title,
    ):
        mock_logged_in.return_value = 1
        mock_update_message.return_value = {
            "message_id": 2,
            "dialog_id": "test-dialog",
            "was_first_user_message": False,
        }

        response = self.client.post("/api/chat/messages/2", json={"content": "Updated later message"})

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
        assert "dialog_title" not in data
        mock_derive_dialog_title.assert_not_called()
        mock_update_dialog_title.assert_not_called()

    @patch("chat_client.core.user_session.is_logged_in")
    def test_delete_dialog_not_authenticated(self, mock_logged_in):
        """Test POST /api/chat/dialogs/{dialog_id} delete when not authenticated"""
        mock_logged_in.return_value = False

        response = self.client.post("/api/chat/dialogs/test-dialog")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] is True
        assert data["redirect"] == "/user/login?next=/chat/test-dialog&reason=auth_required"

    @patch("chat_client.repositories.chat_repository.delete_dialog")
    @patch("chat_client.core.user_session.is_logged_in")
    def test_delete_dialog_authenticated(self, mock_logged_in, mock_delete):
        """Test POST /api/chat/dialogs/{dialog_id} delete when authenticated"""
        mock_logged_in.return_value = 1
        mock_delete.return_value = True

        response = self.client.post("/api/chat/dialogs/test-dialog")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is False
