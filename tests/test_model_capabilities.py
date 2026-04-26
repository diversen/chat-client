from unittest.mock import patch

from chat_client.core import model_capabilities


def test_build_model_capabilities_merges_ollama_detection():
    def resolve_provider_info(_model_name: str) -> dict:
        return {"base_url": "http://localhost:11434/v1", "api_key": "ollama"}

    with patch(
        "chat_client.core.model_capabilities.get_ollama_model_metadata",
        return_value={
            "supports_images": True,
            "supports_tools": True,
            "supports_thinking": True,
            "context_length": 32768,
        },
    ):
        capabilities = model_capabilities.build_model_capabilities(
            models={"qwen3:latest": "ollama", "other-model": {"provider": "openai"}},
            vision_models=[],
            tool_models=[],
            system_message_denylist=[],
            provider_info_resolver=resolve_provider_info,
        )

    assert capabilities["qwen3:latest"] == {
        "supports_images": True,
        "supports_tools": True,
        "supports_attachments": True,
        "supports_reasoning": False,
        "supports_thinking": True,
        "supports_thinking_control": True,
        "supports_system_messages": True,
        "context_length": 32768,
    }
    assert capabilities["other-model"] == {
        "supports_images": False,
        "supports_tools": False,
        "supports_attachments": False,
        "supports_reasoning": False,
        "supports_thinking": False,
        "supports_thinking_control": False,
        "supports_system_messages": True,
        "context_length": None,
    }


def test_resolve_tool_models_includes_detected_ollama_tool_models():
    def resolve_provider_info(_model_name: str) -> dict:
        return {"base_url": "http://localhost:11434/v1", "api_key": "ollama"}

    with patch(
        "chat_client.core.model_capabilities.get_ollama_model_metadata",
        return_value={
            "supports_images": False,
            "supports_tools": True,
            "supports_thinking": False,
            "context_length": 8192,
        },
    ):
        tool_models = model_capabilities.resolve_tool_models(
            models={"qwen3:latest": "ollama", "plain-model": "openai"},
            vision_models=[],
            tool_models=[],
            system_message_denylist=[],
            provider_info_resolver=resolve_provider_info,
        )

    assert tool_models == ["qwen3:latest"]


def test_warm_and_log_model_capabilities_logs_pretty_json():
    class DummyLogger:
        def __init__(self):
            self.messages = []

        def info(self, message, *args):
            if args:
                message = message % args
            self.messages.append(message)

    dummy_logger = DummyLogger()

    with patch(
        "chat_client.core.model_capabilities.get_ollama_model_metadata",
        return_value={
            "supports_images": False,
            "supports_tools": True,
            "supports_thinking": True,
            "context_length": 32768,
        },
    ):
        capabilities = model_capabilities.warm_and_log_model_capabilities(
            logger=dummy_logger,
            models={"qwen3:latest": "ollama"},
            vision_models=[],
            tool_models=[],
            system_message_denylist=[],
            provider_info_resolver=lambda _model_name: {},
        )

    assert capabilities["qwen3:latest"] == {
        "supports_images": False,
        "supports_tools": True,
        "supports_attachments": True,
        "supports_reasoning": False,
        "supports_thinking": True,
        "supports_thinking_control": True,
        "supports_system_messages": True,
        "context_length": 32768,
    }
    assert len(dummy_logger.messages) == 1
    assert (
        dummy_logger.messages[0]
        == 'Model capabilities detected at startup:\n{\n  "qwen3:latest": {\n    "context_length": 32768,\n    "provider": "ollama",\n    "supports_attachments": true,\n    "supports_images": false,\n    "supports_reasoning": false,\n    "supports_system_messages": true,\n    "supports_thinking": true,\n    "supports_thinking_control": true,\n    "supports_tools": true\n  }\n}'
    )


def test_build_model_capabilities_uses_snapshot_cache():
    model_capabilities.clear_model_capabilities_cache()

    def resolve_provider_info(_model_name: str) -> dict:
        return {"base_url": "http://localhost:11434/v1", "api_key": "ollama"}

    with patch(
        "chat_client.core.model_capabilities.get_ollama_model_metadata",
        return_value={
            "supports_images": False,
            "supports_tools": True,
            "supports_thinking": True,
            "context_length": 16384,
        },
    ) as mock_get_ollama_model_metadata:
        first = model_capabilities.build_model_capabilities(
            models={"qwen3:latest": "ollama"},
            vision_models=[],
            tool_models=[],
            system_message_denylist=[],
            provider_info_resolver=resolve_provider_info,
            cache_token={"providers": {"ollama": {"base_url": "http://localhost:11434/v1", "api_key": "ollama"}}},
        )
        second = model_capabilities.build_model_capabilities(
            models={"qwen3:latest": "ollama"},
            vision_models=[],
            tool_models=[],
            system_message_denylist=[],
            provider_info_resolver=resolve_provider_info,
            cache_token={"providers": {"ollama": {"base_url": "http://localhost:11434/v1", "api_key": "ollama"}}},
        )

    assert first == second
    assert mock_get_ollama_model_metadata.call_count == 1


def test_build_model_capabilities_denies_system_messages_for_denylist():
    def resolve_provider_info(_model_name: str) -> dict:
        return {"base_url": "http://localhost:11434/v1", "api_key": "ollama"}

    with patch(
        "chat_client.core.model_capabilities.get_ollama_model_metadata",
        return_value={
            "supports_images": False,
            "supports_tools": False,
            "supports_thinking": False,
            "context_length": 4096,
        },
    ):
        capabilities = model_capabilities.build_model_capabilities(
            models={"blocked-model": "ollama"},
            vision_models=[],
            tool_models=[],
            system_message_denylist=["blocked-model"],
            provider_info_resolver=resolve_provider_info,
        )

    assert capabilities["blocked-model"]["supports_system_messages"] is False
    assert capabilities["blocked-model"]["context_length"] == 4096


def test_build_model_capabilities_merges_openai_reasoning_detection():
    with patch(
        "chat_client.core.model_capabilities.get_openai_model_metadata",
        return_value={
            "supports_reasoning": True,
            "supports_thinking": True,
            "context_length": None,
        },
    ):
        capabilities = model_capabilities.build_model_capabilities(
            models={"gpt-5.1": "openai", "gpt-5.4-nano": "openai"},
            vision_models=[],
            tool_models=[],
            system_message_denylist=[],
            provider_info_resolver=lambda _model_name: {"api_key": "key", "base_url": "https://api.openai.com/v1"},
            cache_token={"models": {"gpt-5.1": "openai", "gpt-5.4-nano": "openai"}},
        )

    assert capabilities["gpt-5.1"]["supports_reasoning"] is True
    assert capabilities["gpt-5.1"]["supports_thinking"] is True
    assert capabilities["gpt-5.1"]["supports_thinking_control"] is True


def test_build_model_capabilities_probes_openai_reasoning_with_tools_for_tool_models():
    with patch(
        "chat_client.core.model_capabilities.get_openai_model_metadata",
        return_value={
            "supports_reasoning": False,
            "supports_thinking": False,
            "context_length": None,
        },
    ) as mock_get_openai_model_metadata:
        model_capabilities.build_model_capabilities(
            models={"gpt-5.4-nano": "openai"},
            vision_models=[],
            tool_models=["gpt-5.4-nano"],
            system_message_denylist=[],
            provider_info_resolver=lambda _model_name: {"api_key": "key", "base_url": "https://api.openai.com/v1"},
            cache_token={"models": {"gpt-5.4-nano": "openai"}, "tool_models": ["gpt-5.4-nano"]},
        )

    assert mock_get_openai_model_metadata.call_args.kwargs["probe_tools"] is True


def test_supports_model_thinking_control_uses_built_capabilities():
    with patch(
        "chat_client.core.model_capabilities.get_ollama_model_metadata",
        return_value={
            "supports_images": False,
            "supports_tools": False,
            "supports_thinking": True,
            "context_length": 8192,
        },
    ):
        assert model_capabilities.supports_model_thinking_control(
            model_name="qwen3:latest",
            models={"qwen3:latest": "ollama"},
            vision_models=[],
            tool_models=[],
            system_message_denylist=[],
            provider_info_resolver=lambda _model_name: {"base_url": "http://localhost:11434/v1", "api_key": "ollama"},
        ) is True
