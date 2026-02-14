from unittest.mock import MagicMock, patch

import httpx

from chat_client.core import mcp_client


def _mock_httpx_response(payload: dict, status_code: int = 200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_get_openai_tools_from_mcp_maps_tools():
    responses = [
        _mock_httpx_response({"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}),
        _mock_httpx_response(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo text",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"text": {"type": "string"}},
                                "required": ["text"],
                            },
                        }
                    ]
                },
            }
        ),
    ]

    with patch("chat_client.core.mcp_client.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.side_effect = responses
        mock_client_cls.return_value.__enter__.return_value = mock_client

        tools = mcp_client.get_openai_tools_from_mcp(
            server_url="https://example.test/mcp",
            timeout_seconds=5.0,
            auth_token="token",
            logger=MagicMock(),
        )

    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "echo"


def test_execute_tool_call_via_mcp_returns_text():
    responses = [
        _mock_httpx_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": "Echo: hi"}],
                    "isError": False,
                },
            }
        )
    ]

    with patch("chat_client.core.mcp_client.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.side_effect = responses
        mock_client_cls.return_value.__enter__.return_value = mock_client

        text = mcp_client.execute_tool_call_via_mcp(
            tool_call={"function": {"name": "echo", "arguments": '{"text":"hi"}'}},
            server_url="https://example.test/mcp",
            timeout_seconds=5.0,
            auth_token=None,
            logger=MagicMock(),
        )

    assert text == "Echo: hi"


def test_execute_tool_call_via_mcp_handles_invalid_payload():
    logger = MagicMock()
    text = mcp_client.execute_tool_call_via_mcp(
        tool_call={"function": {"name": "echo", "arguments": '"not-an-object"'}},
        server_url="https://example.test/mcp",
        timeout_seconds=5.0,
        auth_token=None,
        logger=logger,
    )
    assert "Invalid tool call payload" in text


def test_headers_accept_include_event_stream():
    headers = mcp_client._headers(auth_token=None)
    assert headers["Accept"] == "application/json, text/event-stream"


def test_headers_context7_include_api_key_header():
    headers = mcp_client._headers(auth_token="ctx7sk-test", server_url="https://mcp.context7.com/mcp")
    assert headers["CONTEXT7_API_KEY"] == "ctx7sk-test"


def test_get_openai_tools_from_mcp_oauth_406_logs_and_returns_empty():
    logger = MagicMock()

    request = httpx.Request("POST", "https://mcp.context7.com/mcp/oauth")
    response = httpx.Response(status_code=406, request=request)
    status_error = httpx.HTTPStatusError("not acceptable", request=request, response=response)

    failing_response = MagicMock()
    failing_response.raise_for_status.side_effect = status_error

    with patch("chat_client.core.mcp_client.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.post.return_value = failing_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        tools = mcp_client.get_openai_tools_from_mcp(
            server_url="https://mcp.context7.com/mcp/oauth",
            timeout_seconds=5.0,
            auth_token="token",
            logger=logger,
        )

    assert tools == []
    logged_exception_message = logger.exception.call_args[0][0]
    assert logged_exception_message == "Failed to fetch tools from MCP server"
