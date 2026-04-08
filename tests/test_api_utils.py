from unittest.mock import patch

import httpx

from chat_client.core import api_utils


class DummyResponse:
    def __init__(self, payload, status_code: int = 200, url: str = "http://127.0.0.1:11434/api/show"):
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", url)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "status error",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_get_ollama_model_capabilities_reads_show_capabilities():
    api_utils._OLLAMA_MODEL_METADATA_CACHE.clear()
    client = DummyClient(
        [
            DummyResponse({"capabilities": ["vision", "thinking"], "model_info": {"llama.context_length": 8192}}),
            DummyResponse({"message": {"content": "ok"}}),
        ]
    )

    with patch("chat_client.core.api_utils.httpx.Client", return_value=client):
        capabilities = api_utils.get_ollama_model_capabilities(
            {"base_url": "http://127.0.0.1:11434/v1", "api_key": "ollama"},
            "qwen3:latest",
        )

    assert capabilities == {
        "supports_images": True,
        "supports_tools": True,
        "supports_thinking": True,
    }
    assert client.calls[0]["url"] == "http://127.0.0.1:11434/api/show"
    assert client.calls[1]["url"] == "http://127.0.0.1:11434/api/chat"


def test_get_ollama_model_capabilities_returns_false_tools_when_probe_fails():
    api_utils._OLLAMA_MODEL_METADATA_CACHE.clear()
    client = DummyClient(
        [
            DummyResponse({"capabilities": []}),
            httpx.HTTPStatusError(
                "unsupported tools",
                request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
                response=httpx.Response(400, request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat")),
            ),
        ]
    )

    with patch("chat_client.core.api_utils.httpx.Client", return_value=client):
        capabilities = api_utils.get_ollama_model_capabilities(
            {"base_url": "http://127.0.0.1:11434/v1", "api_key": "ollama"},
            "llama3.2:latest",
        )

    assert capabilities == {
        "supports_images": False,
        "supports_tools": False,
        "supports_thinking": False,
    }


def test_get_ollama_model_metadata_includes_context_length():
    api_utils._OLLAMA_MODEL_METADATA_CACHE.clear()
    client = DummyClient(
        [
            DummyResponse({"capabilities": ["tools"], "model_info": {"qwen2.context_length": 32768}}),
        ]
    )

    with patch("chat_client.core.api_utils.httpx.Client", return_value=client):
        metadata = api_utils.get_ollama_model_metadata(
            {"base_url": "http://127.0.0.1:11434/v1", "api_key": "ollama"},
            "qwen3:latest",
        )

    assert metadata == {
        "supports_images": False,
        "supports_tools": True,
        "supports_thinking": False,
        "context_length": 32768,
    }
