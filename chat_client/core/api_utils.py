from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from openai import OpenAI

OLLAMA_CAPABILITY_TIMEOUT_SECONDS = 5.0

_OLLAMA_MODEL_METADATA_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_OPENAI_MODEL_METADATA_CACHE: dict[tuple[str, str, bool], dict[str, Any]] = {}


def get_provider_models(provider: dict):
    """
    Helper to get all ollama models
    """
    client = OpenAI(**provider)
    ollama_model_names = []
    ollama_models = client.models.list()
    for model in ollama_models:
        model_name = model.id
        ollama_model_names.append(model_name)

    ollama_model_names.sort()
    return ollama_model_names


def _normalize_ollama_api_base_url(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if not normalized:
        return ""

    parsed = urlsplit(normalized)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    if not path.endswith("/api"):
        path = f"{path}/api" if path else "/api"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _build_ollama_headers(api_key: str) -> dict[str, str]:
    key = str(api_key or "").strip()
    if not key or key == "ollama":
        return {}
    return {"Authorization": f"Bearer {key}"}


def _extract_ollama_capability_flags(show_payload: dict[str, Any], model_name: str) -> dict[str, bool]:
    capabilities = show_payload.get("capabilities", [])
    normalized_capabilities = {str(capability).strip().lower() for capability in capabilities if isinstance(capability, (str, int, float))}
    normalized_name = str(model_name or "").strip().lower()
    return {
        "supports_images": "vision" in normalized_capabilities,
        "supports_tools": "tools" in normalized_capabilities or "tool" in normalized_capabilities,
        "supports_thinking": (
            "thinking" in normalized_capabilities or "reasoning" in normalized_capabilities or "thinking" in normalized_name
        ),
    }


def _extract_ollama_context_length(show_payload: dict[str, Any]) -> int | None:
    model_info = show_payload.get("model_info")
    if isinstance(model_info, dict):
        for key, value in model_info.items():
            normalized_key = str(key or "").strip().lower()
            if normalized_key.endswith(".context_length"):
                try:
                    context_length = int(value)
                except (TypeError, ValueError):
                    continue
                if context_length > 0:
                    return context_length

    parameters = str(show_payload.get("parameters", "") or "")
    for raw_line in parameters.splitlines():
        line = raw_line.strip()
        if not line.lower().startswith("num_ctx"):
            continue
        _, _, value = line.partition(" ")
        try:
            context_length = int(value.strip())
        except (TypeError, ValueError):
            continue
        if context_length > 0:
            return context_length

    return None


def _ollama_post(
    api_base_url: str,
    endpoint: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(
            f"{api_base_url}/{endpoint.lstrip('/')}",
            json=payload,
            headers=_build_ollama_headers(api_key),
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        return {}
    return data


def _ollama_model_accepts_tools(
    api_base_url: str,
    *,
    model_name: str,
    api_key: str,
    timeout_seconds: float,
) -> bool:
    try:
        _ollama_post(
            api_base_url,
            "chat",
            {
                "model": model_name,
                "stream": False,
                "messages": [{"role": "user", "content": "Reply with ok. Do not call any tools."}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "noop",
                            "description": "Do nothing.",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "additionalProperties": False,
                            },
                        },
                    }
                ],
            },
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
    except Exception:
        return False
    return True


def get_ollama_model_metadata(provider: dict[str, Any], model_name: str) -> dict[str, Any]:
    """
    Best-effort Ollama metadata detection.

    `supports_tools` means the model safely accepts a `tools` payload.
    `supports_thinking` is informational only and should not be used to gate requests.
    """
    if not isinstance(provider, dict):
        return {}

    api_base_url = _normalize_ollama_api_base_url(str(provider.get("base_url", "")))
    normalized_model_name = str(model_name or "").strip()
    if not api_base_url or not normalized_model_name:
        return {}

    cache_key = (api_base_url, normalized_model_name)
    cached = _OLLAMA_MODEL_METADATA_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    timeout_seconds = float(provider.get("timeout_seconds", OLLAMA_CAPABILITY_TIMEOUT_SECONDS) or OLLAMA_CAPABILITY_TIMEOUT_SECONDS)
    api_key = str(provider.get("api_key", "") or "")
    metadata: dict[str, Any] = {
        "supports_images": False,
        "supports_tools": False,
        "supports_thinking": "thinking" in normalized_model_name.lower(),
        "context_length": None,
    }

    try:
        show_payload = _ollama_post(
            api_base_url,
            "show",
            {"model": normalized_model_name},
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        metadata.update(_extract_ollama_capability_flags(show_payload, normalized_model_name))
        metadata["context_length"] = _extract_ollama_context_length(show_payload)
    except Exception:
        _OLLAMA_MODEL_METADATA_CACHE[cache_key] = dict(metadata)
        return dict(metadata)

    if not metadata["supports_tools"]:
        metadata["supports_tools"] = _ollama_model_accepts_tools(
            api_base_url,
            model_name=normalized_model_name,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

    _OLLAMA_MODEL_METADATA_CACHE[cache_key] = dict(metadata)
    return dict(metadata)


def get_ollama_model_capabilities(provider: dict[str, Any], model_name: str) -> dict[str, bool]:
    metadata = get_ollama_model_metadata(provider, model_name)
    return {
        "supports_images": bool(metadata.get("supports_images")),
        "supports_tools": bool(metadata.get("supports_tools")),
        "supports_thinking": bool(metadata.get("supports_thinking")),
    }


def get_openai_model_metadata(provider: dict[str, Any], model_name: str, *, probe_tools: bool = False) -> dict[str, Any]:
    """
    Best-effort OpenAI metadata detection.

    `supports_reasoning` and `supports_thinking` are inferred by probing a small
    Chat Completions API call with reasoning enabled. Failure is treated as unsupported.
    """
    if not isinstance(provider, dict):
        return {}

    normalized_model_name = str(model_name or "").strip()
    base_url = str(provider.get("base_url", "") or "").strip()
    if not normalized_model_name:
        return {}

    cache_key = (base_url, normalized_model_name, bool(probe_tools))
    cached = _OPENAI_MODEL_METADATA_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    metadata: dict[str, Any] = {
        "supports_reasoning": False,
        "supports_thinking": False,
        "context_length": None,
    }

    try:
        timeout_seconds = float(provider.get("timeout_seconds", OLLAMA_CAPABILITY_TIMEOUT_SECONDS) or OLLAMA_CAPABILITY_TIMEOUT_SECONDS)
        client = OpenAI(
            api_key=provider.get("api_key"),
            base_url=base_url or None,
            timeout=timeout_seconds,
        )
        create_kwargs: dict[str, Any] = {
            "model": normalized_model_name,
            "messages": [{"role": "user", "content": "Say OK."}],
            "reasoning_effort": "low",
            "stream": False,
            "max_completion_tokens": 10,
        }
        if probe_tools:
            create_kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "noop",
                        "description": "Do nothing.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    },
                }
            ]
        client.chat.completions.create(**create_kwargs)
        metadata["supports_reasoning"] = True
        metadata["supports_thinking"] = True
    except Exception:
        _OPENAI_MODEL_METADATA_CACHE[cache_key] = dict(metadata)
        return dict(metadata)

    _OPENAI_MODEL_METADATA_CACHE[cache_key] = dict(metadata)
    return dict(metadata)
