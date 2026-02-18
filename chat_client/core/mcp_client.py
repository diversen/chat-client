import json
import uuid
from typing import Any

import httpx


class MCPClientError(Exception):
    """
    Raised when an MCP server request fails.
    """


def _build_headers(auth_token: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = auth_token.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _extract_jsonrpc_result(payload: dict[str, Any]) -> Any:
    if "error" in payload and payload["error"] is not None:
        error = payload["error"]
        message = "MCP server returned an error"
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            message = error["message"]
        raise MCPClientError(message)

    if "result" not in payload:
        raise MCPClientError("MCP server response missing result")

    return payload["result"]


def _post_jsonrpc(
    server_url: str,
    auth_token: str,
    timeout_seconds: float,
    method: str,
    params: dict[str, Any],
) -> Any:
    url = server_url.strip()
    if not url:
        raise MCPClientError("MCP_SERVER_URL is empty")

    body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json=body, headers=_build_headers(auth_token))
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as error:
        raise MCPClientError("MCP request timed out") from error
    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code
        if status_code in (401, 403):
            raise MCPClientError("MCP authentication failed") from error
        raise MCPClientError(f"MCP request failed with status {status_code}") from error
    except httpx.HTTPError as error:
        raise MCPClientError("MCP request failed") from error
    except ValueError as error:
        raise MCPClientError("MCP server returned invalid JSON") from error

    if not isinstance(payload, dict):
        raise MCPClientError("MCP server returned invalid JSON-RPC payload")

    return _extract_jsonrpc_result(payload)


def list_tools_openai_schema(server_url: str, auth_token: str, timeout_seconds: float) -> list[dict[str, Any]]:
    """
    Load MCP tools and transform them into OpenAI-compatible tool definitions.
    """
    result = _post_jsonrpc(
        server_url=server_url,
        auth_token=auth_token,
        timeout_seconds=timeout_seconds,
        method="tools/list",
        params={},
    )

    tools = result.get("tools", []) if isinstance(result, dict) else []
    if not isinstance(tools, list):
        raise MCPClientError("MCP tools/list returned invalid tools format")

    openai_tools: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue

        name = tool.get("name")
        if not isinstance(name, str) or not name.strip():
            continue

        description = tool.get("description", "")
        input_schema = tool.get("inputSchema", {"type": "object", "properties": {}})
        if not isinstance(input_schema, dict):
            input_schema = {"type": "object", "properties": {}}

        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description if isinstance(description, str) else "",
                    "parameters": input_schema,
                },
            }
        )

    return openai_tools


def _normalize_tool_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
            else:
                parts.append(json.dumps(item))
        return "\n".join(parts)

    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        return json.dumps(content)

    return str(content)


def call_tool(server_url: str, auth_token: str, timeout_seconds: float, name: str, arguments: dict[str, Any]) -> str:
    """
    Execute an MCP tool call and return normalized text content.
    """
    result = _post_jsonrpc(
        server_url=server_url,
        auth_token=auth_token,
        timeout_seconds=timeout_seconds,
        method="tools/call",
        params={"name": name, "arguments": arguments},
    )

    if isinstance(result, dict):
        if result.get("isError"):
            content = _normalize_tool_content(result.get("content", "Tool execution failed"))
            raise MCPClientError(content)
        return _normalize_tool_content(result.get("content", ""))

    return _normalize_tool_content(result)
