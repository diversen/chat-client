import json
import logging
from typing import Any, Callable

from chat_client.core.api_utils import get_ollama_model_metadata, get_openai_model_metadata

_MODEL_CAPABILITIES_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


def resolve_model_provider_name(models: dict[str, Any], model_name: str) -> str:
    model_config = models.get(model_name, "")
    if isinstance(model_config, str):
        return model_config
    if isinstance(model_config, dict):
        provider_name = model_config.get("provider", "")
        if isinstance(provider_name, str):
            return provider_name
    return ""


def clear_model_capabilities_cache() -> None:
    _MODEL_CAPABILITIES_CACHE.clear()


def _normalize_cache_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_cache_value(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize_cache_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _build_cache_key(
    *,
    models: dict[str, Any],
    vision_models: list[str] | None,
    tool_models: list[str] | None,
    system_message_denylist: list[str] | None,
    cache_token: Any = None,
) -> str:
    payload = {
        "models": _normalize_cache_value(models),
        "vision_models": _normalize_cache_value(vision_models if isinstance(vision_models, list) else []),
        "tool_models": _normalize_cache_value(tool_models if isinstance(tool_models, list) else []),
        "system_message_denylist": _normalize_cache_value(system_message_denylist if isinstance(system_message_denylist, list) else []),
        "cache_token": _normalize_cache_value(cache_token),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _supports_system_messages_for_model(model_name: str, system_message_denylist: set[str]) -> bool:
    return model_name not in system_message_denylist


def supports_thinking_control(details: dict[str, Any] | None) -> bool:
    if not isinstance(details, dict):
        return False
    return bool(details.get("supports_reasoning") or details.get("supports_thinking"))


def build_model_capabilities(
    *,
    models: dict[str, Any],
    vision_models: list[str] | None,
    tool_models: list[str] | None,
    system_message_denylist: list[str] | None,
    provider_info_resolver: Callable[[str], dict[str, Any]],
    cache_token: Any = None,
) -> dict[str, dict[str, Any]]:
    cache_key = _build_cache_key(
        models=models,
        vision_models=vision_models,
        tool_models=tool_models,
        system_message_denylist=system_message_denylist,
        cache_token=cache_token,
    )
    cached = _MODEL_CAPABILITIES_CACHE.get(cache_key)
    if cached is not None:
        return {model_name: dict(details) for model_name, details in cached.items()}

    configured_vision_models = set(vision_models if isinstance(vision_models, list) else [])
    configured_system_message_denylist = set(system_message_denylist if isinstance(system_message_denylist, list) else [])
    configured_tool_models: set[str] = set()
    if isinstance(tool_models, list):
        if "*" in tool_models:
            configured_tool_models = set(models.keys())
        else:
            configured_tool_models = set(tool_models)

    capabilities: dict[str, dict[str, Any]] = {}
    for model_name in models.keys():
        detected_capabilities: dict[str, Any] = {}
        provider_name = resolve_model_provider_name(models, model_name)
        if provider_name == "ollama":
            detected_capabilities = get_ollama_model_metadata(provider_info_resolver(model_name), model_name)
        elif provider_name == "openai":
            detected_capabilities = get_openai_model_metadata(
                provider_info_resolver(model_name),
                model_name,
                probe_tools=model_name in configured_tool_models,
            )

        supports_images = model_name in configured_vision_models or bool(detected_capabilities.get("supports_images"))
        supports_tools = model_name in configured_tool_models or bool(detected_capabilities.get("supports_tools"))
        supports_system_messages = _supports_system_messages_for_model(model_name, configured_system_message_denylist)
        capabilities[model_name] = {
            "supports_images": supports_images,
            "supports_tools": supports_tools,
            "supports_attachments": supports_tools,
            "supports_reasoning": bool(detected_capabilities.get("supports_reasoning")),
            "supports_thinking": bool(detected_capabilities.get("supports_thinking")),
            "supports_thinking_control": supports_thinking_control(detected_capabilities),
            "supports_system_messages": supports_system_messages,
            "context_length": detected_capabilities.get("context_length"),
        }
    _MODEL_CAPABILITIES_CACHE[cache_key] = {model_name: dict(details) for model_name, details in capabilities.items()}
    return {model_name: dict(details) for model_name, details in capabilities.items()}


def resolve_tool_models(
    *,
    models: dict[str, Any],
    vision_models: list[str] | None,
    tool_models: list[str] | None,
    system_message_denylist: list[str] | None,
    provider_info_resolver: Callable[[str], dict[str, Any]],
    cache_token: Any = None,
) -> list[str]:
    capabilities = build_model_capabilities(
        models=models,
        vision_models=vision_models,
        tool_models=tool_models,
        system_message_denylist=system_message_denylist,
        provider_info_resolver=provider_info_resolver,
        cache_token=cache_token,
    )
    return [model_name for model_name, details in capabilities.items() if details.get("supports_tools")]


def supports_model_images(
    *,
    model_name: str,
    models: dict[str, Any],
    vision_models: list[str] | None,
    tool_models: list[str] | None,
    system_message_denylist: list[str] | None,
    provider_info_resolver: Callable[[str], dict[str, Any]],
    cache_token: Any = None,
) -> bool:
    capabilities = build_model_capabilities(
        models=models,
        vision_models=vision_models,
        tool_models=tool_models,
        system_message_denylist=system_message_denylist,
        provider_info_resolver=provider_info_resolver,
        cache_token=cache_token,
    )
    return bool(capabilities.get(model_name, {}).get("supports_images"))


def supports_model_attachments(
    *,
    model_name: str,
    models: dict[str, Any],
    vision_models: list[str] | None,
    tool_models: list[str] | None,
    system_message_denylist: list[str] | None,
    provider_info_resolver: Callable[[str], dict[str, Any]],
    cache_token: Any = None,
) -> bool:
    capabilities = build_model_capabilities(
        models=models,
        vision_models=vision_models,
        tool_models=tool_models,
        system_message_denylist=system_message_denylist,
        provider_info_resolver=provider_info_resolver,
        cache_token=cache_token,
    )
    return bool(capabilities.get(model_name, {}).get("supports_attachments"))


def supports_model_thinking_control(
    *,
    model_name: str,
    models: dict[str, Any],
    vision_models: list[str] | None,
    tool_models: list[str] | None,
    system_message_denylist: list[str] | None,
    provider_info_resolver: Callable[[str], dict[str, Any]],
    cache_token: Any = None,
) -> bool:
    capabilities = build_model_capabilities(
        models=models,
        vision_models=vision_models,
        tool_models=tool_models,
        system_message_denylist=system_message_denylist,
        provider_info_resolver=provider_info_resolver,
        cache_token=cache_token,
    )
    return bool(capabilities.get(model_name, {}).get("supports_thinking_control"))


def warm_and_log_model_capabilities(
    *,
    logger: logging.Logger,
    models: dict[str, Any],
    vision_models: list[str] | None,
    tool_models: list[str] | None,
    system_message_denylist: list[str] | None,
    provider_info_resolver: Callable[[str], dict[str, Any]],
    cache_token: Any = None,
) -> dict[str, dict[str, Any]]:
    capabilities = build_model_capabilities(
        models=models,
        vision_models=vision_models,
        tool_models=tool_models,
        system_message_denylist=system_message_denylist,
        provider_info_resolver=provider_info_resolver,
        cache_token=cache_token,
    )

    if not capabilities:
        logger.info("Model capabilities detected at startup: {}")
        return capabilities

    payload = {
        model_name: {
            **details,
            "provider": resolve_model_provider_name(models, model_name) or "unknown",
        }
        for model_name, details in sorted(capabilities.items())
    }
    logger.info("Model capabilities detected at startup:\n%s", json.dumps(payload, indent=2, sort_keys=True))
    return capabilities
