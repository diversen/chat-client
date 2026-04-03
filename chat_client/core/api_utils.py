from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from openai import OpenAI

OLLAMA_CAPABILITY_TIMEOUT_SECONDS = 5.0

_OLLAMA_CAPABILITY_CACHE: dict[tuple[str, str], dict[str, bool]] = {}


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
    normalized_capabilities = {
        str(capability).strip().lower()
        for capability in capabilities
        if isinstance(capability, (str, int, float))
    }
    normalized_name = str(model_name or "").strip().lower()
    return {
        "supports_images": "vision" in normalized_capabilities,
        "supports_tools": "tools" in normalized_capabilities or "tool" in normalized_capabilities,
        "supports_thinking": (
            "thinking" in normalized_capabilities
            or "reasoning" in normalized_capabilities
            or "thinking" in normalized_name
        ),
    }


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


def get_ollama_model_capabilities(provider: dict[str, Any], model_name: str) -> dict[str, bool]:
    """
    Best-effort Ollama capability detection.

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
    cached = _OLLAMA_CAPABILITY_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    timeout_seconds = float(provider.get("timeout_seconds", OLLAMA_CAPABILITY_TIMEOUT_SECONDS) or OLLAMA_CAPABILITY_TIMEOUT_SECONDS)
    api_key = str(provider.get("api_key", "") or "")
    capabilities = {
        "supports_images": False,
        "supports_tools": False,
        "supports_thinking": "thinking" in normalized_model_name.lower(),
    }

    try:
        show_payload = _ollama_post(
            api_base_url,
            "show",
            {"model": normalized_model_name},
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        capabilities.update(_extract_ollama_capability_flags(show_payload, normalized_model_name))
    except Exception:
        _OLLAMA_CAPABILITY_CACHE[cache_key] = dict(capabilities)
        return dict(capabilities)

    if not capabilities["supports_tools"]:
        capabilities["supports_tools"] = _ollama_model_accepts_tools(
            api_base_url,
            model_name=normalized_model_name,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

    _OLLAMA_CAPABILITY_CACHE[cache_key] = dict(capabilities)
    return dict(capabilities)
