from unittest.mock import patch

import pytest
import httpx

from chat_client.core import mcp_client


class DummyResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "http://127.0.0.1:5000/mcp")

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
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, *_args, **_kwargs):
        if self._exception:
            raise self._exception
        return self._response


def test_list_tools_openai_schema_success():
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "tools": [
                {
                    "name": "search_docs",
                    "description": "Search docs",
                    "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
                }
            ]
        },
    }
    with patch("chat_client.core.mcp_client.httpx.Client", return_value=DummyClient(response=DummyResponse(payload))):
        tools = mcp_client.list_tools_openai_schema("http://127.0.0.1:5000/mcp", "", 5.0)

    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "search_docs"
    assert tools[0]["function"]["parameters"]["type"] == "object"


def test_call_tool_success_text_content_list():
    payload = {
        "jsonrpc": "2.0",
        "id": "2",
        "result": {"content": [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}], "isError": False},
    }
    with patch("chat_client.core.mcp_client.httpx.Client", return_value=DummyClient(response=DummyResponse(payload))):
        result = mcp_client.call_tool("http://127.0.0.1:5000/mcp", "", 5.0, "echo", {"text": "x"})

    assert result == "hello\nworld"


def test_jsonrpc_error_is_raised():
    payload = {"jsonrpc": "2.0", "id": "3", "error": {"message": "tool exploded"}}
    with patch("chat_client.core.mcp_client.httpx.Client", return_value=DummyClient(response=DummyResponse(payload))):
        with pytest.raises(mcp_client.MCPClientError, match="tool exploded"):
            mcp_client.call_tool("http://127.0.0.1:5000/mcp", "", 5.0, "echo", {})


def test_http_401_maps_to_auth_error():
    with patch(
        "chat_client.core.mcp_client.httpx.Client",
        return_value=DummyClient(response=DummyResponse({"x": "y"}, status_code=401)),
    ):
        with pytest.raises(mcp_client.MCPClientError, match="authentication failed"):
            mcp_client.list_tools_openai_schema("http://127.0.0.1:5000/mcp", "token", 5.0)


def test_timeout_maps_to_mcp_timeout():
    with patch(
        "chat_client.core.mcp_client.httpx.Client",
        return_value=DummyClient(exception=httpx.TimeoutException("timeout")),
    ):
        with pytest.raises(mcp_client.MCPClientError, match="timed out"):
            mcp_client.list_tools_openai_schema("http://127.0.0.1:5000/mcp", "", 5.0)
