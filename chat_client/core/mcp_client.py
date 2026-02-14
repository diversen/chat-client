import json
import logging
from typing import Any

import httpx


class MCPClientError(Exception):
    pass


def _headers(auth_token: str | None, server_url: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        # MCP over HTTP commonly negotiates either JSON or SSE responses.
        "Accept": "application/json, text/event-stream",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
        if server_url and "context7.com" in server_url:
            headers["CONTEXT7_API_KEY"] = auth_token
    return headers


def _to_openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    openai_tools: list[dict[str, Any]] = []
    for tool in mcp_tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        description = tool.get("description", "")
        schema = tool.get("inputSchema", {"type": "object", "properties": {}})
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": schema,
                },
            }
        )
    return openai_tools


class MCPHTTPClient:
    def __init__(self, server_url: str, timeout_seconds: float = 15.0, auth_token: str | None = None):
        self.server_url = server_url
        self.timeout_seconds = timeout_seconds
        self.auth_token = auth_token
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    self.server_url,
                    headers=_headers(self.auth_token, self.server_url),
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 406 and self.server_url.rstrip("/").endswith("/oauth"):
                raise MCPClientError(
                    "MCP server returned 406 for an OAuth endpoint. "
                    "This client supports direct HTTP token auth, not interactive OAuth redirect flow. "
                    "Use the non-OAuth MCP endpoint (for Context7: '/mcp') with a token, or add an OAuth flow."
                ) from exc
            raise MCPClientError(f"MCP request failed for method '{method}': {exc}") from exc
        except Exception as exc:
            raise MCPClientError(f"MCP request failed for method '{method}': {exc}") from exc

        if not isinstance(data, dict):
            raise MCPClientError(f"MCP response for method '{method}' was not an object")

        error = data.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", "Unknown MCP error"))
            raise MCPClientError(f"MCP method '{method}' failed: {message}")

        result = data.get("result")
        if not isinstance(result, dict):
            raise MCPClientError(f"MCP response for method '{method}' did not contain an object result")
        return result

    def initialize(self) -> dict[str, Any]:
        return self.call(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "chat-client", "version": "unknown"},
            },
        )

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.call("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise MCPClientError("MCP tools/list returned invalid tools payload")
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self.call("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        if not isinstance(content, list) or not content:
            return ""
        first = content[0]
        if isinstance(first, dict):
            text = first.get("text")
            if isinstance(text, str):
                return text
        return ""


def get_openai_tools_from_mcp(server_url: str, timeout_seconds: float, auth_token: str | None, logger: logging.Logger) -> list[dict[str, Any]]:
    client = MCPHTTPClient(server_url, timeout_seconds=timeout_seconds, auth_token=auth_token)
    try:
        logger.info("Fetching MCP tools from %s", server_url)
        client.initialize()
        mcp_tools = client.list_tools()
        openai_tools = _to_openai_tools(mcp_tools)
        tool_names = [tool.get("function", {}).get("name", "<unknown>") for tool in openai_tools]
        logger.info("Fetched %d MCP tools from %s", len(openai_tools), server_url)
        if tool_names:
            logger.info("MCP tool names: %s", ", ".join(tool_names))
        else:
            logger.info("MCP tool list is empty")
        return openai_tools
    except MCPClientError:
        logger.exception("Failed to fetch tools from MCP server")
        return []


def execute_tool_call_via_mcp(
    tool_call: dict[str, Any],
    server_url: str,
    timeout_seconds: float,
    auth_token: str | None,
    logger: logging.Logger,
) -> str:
    try:
        name = tool_call["function"]["name"]
        raw_args = tool_call["function"]["arguments"]
        arguments = json.loads(raw_args)
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
    except Exception as exc:
        logger.exception("Invalid tool call payload")
        return f"Invalid tool call payload: {exc}"

    logger.info(
        "Calling MCP tool '%s' on %s with argument keys: %s",
        name,
        server_url,
        ", ".join(sorted(arguments.keys())) if arguments else "<none>",
    )
    client = MCPHTTPClient(server_url, timeout_seconds=timeout_seconds, auth_token=auth_token)
    try:
        result = client.call_tool(name=name, arguments=arguments)
        logger.info("MCP tool '%s' completed (output length: %d)", name, len(result))
        preview = result[:256].replace("\n", "\\n")
        logger.info("MCP tool '%s' output preview (256 chars): %s", name, preview)
        return result
    except MCPClientError:
        logger.exception("MCP tool call failed for '%s'", name)
        return "MCP tool call failed"
