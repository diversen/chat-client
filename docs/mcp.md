# MCP Notes

MCP support in `chat-client` is not fully completed, so the main config template does not carry the example block anymore.

Current intended config shape in `data/config.py`:

```python
# MCP server integration (remote JSON-RPC over HTTP)
# Tools are loaded from MCP `tools/list` and executed via MCP `tools/call`.
MCP_SERVER_URL = "http://127.0.0.1:5000/mcp"
MCP_AUTH_TOKEN = "your-very-secret-token"
MCP_TIMEOUT_SECONDS = 20.0
MCP_TOOLS_CACHE_SECONDS = 60.0
```

Hosted example:

```python
MCP_SERVER_URL = "https://mcp.context7.com/mcp"
MCP_AUTH_TOKEN = "ctx7sk-..."
```

Related config:

- `TOOL_MODELS` controls which models receive tool definitions.
- `TOOL_REGISTRY` and `LOCAL_TOOL_DEFINITIONS` are preferred over MCP when local tools are configured.
