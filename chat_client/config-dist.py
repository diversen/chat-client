import logging
from pathlib import Path
from chat_client.tools.python_tool import python_hardened as python_hardened_tool


# SMTP
class ConfigSMTP:

    HOST = "smtp-relay.brevo.com"
    PORT = 587
    USERNAME = "user@mail.dk"
    PASSWORD = "password"
    DEFAULT_FROM = "Chat <mail@10kilobyte.com>"


# Set a Default model
# DEFAULT_MODEL = "deepseek-r1:14b"

# Logging
LOG_LEVEL = logging.INFO

# Reloading when code changes
RELOAD = True

# Data path for logs and database
DATA_DIR = "data"
DATABASE = Path(DATA_DIR) / Path("database.db")

# Used when sending emails
HOSTNAME_WITH_SCHEME = "https://home.10kilobyte.com"
SITE_NAME = "home.10kilobyte.com"

# Session key
SESSION_SECRET_KEY = "SECRET_KEY_SADFDFREQ2134324AADFDGFFGMIESDF"

# Session cookie name (helps avoid collisions with other apps on the same host)
SESSION_COOKIE = "chat_client_session"

# Session HTTPS only
SESSION_HTTPS_ONLY = True  # Set to True if using HTTPS

# Maximum accepted HTTP request body size in bytes (default 10 MB)
REQUEST_MAX_SIZE = 10 * 1024 * 1024

# Use mathjax for rendering math
USE_KATEX = True

# Timeout for the built-in python tools in seconds.
# Set to 0 for no timeout.
PYTHON_TOOL_TIMEOUT_SECONDS = 60

# Uploaded files available to tools are stored privately here before being mounted into Docker.
ATTACHMENT_STORAGE_DIR = Path(DATA_DIR) / Path("attachments")
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
PYTHON_TOOL_ATTACHMENT_MOUNT_DIR = "/mnt/data"

# Maximum number of model-response rounds used to produce a single assistant reply.
# This includes tool-calling rounds and the final no-tool answer round.
CHAT_MAX_LOOP_ROUNDS = 8

PROVIDERS = {
    # "openai": {
    #     "base_url": "https://api.openai.com/v1",
    #     "api_key": "API_KEY",
    # },
    # "gemini": {
    #     "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    #     "api_key": "API_KEY",
    # },
    # "vllm": {
    #     "base_url": "http://localhost:8000/v1",
    #     "api_key": "ollama",
    # },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
}

# Set a Default model
# DEFAULT_MODEL = "deepseek-r1:14b"

MODELS = {
    # "gpt-5-nano": "openai",
    # "gemma-3-27b-it": "gemini",
}
# Ollama models are discovered automatically from the configured provider at runtime.

# Enable vision models (models that can process both text and images)
VISION_MODELS: list[str] = []

# System models are models that are capable of injecting initial system instruction into the model template.
# Not all models supports this, so we need to specify which models that should receive system instructions.
SYSTEM_MESSAGE_MODELS: list = []

# Optional local tool registry (preferred over MCP when configured).
# Functions must be callables that accept keyword arguments.


TOOL_REGISTRY = {
    "python_tool": python_hardened_tool,
}


# Optional explicit local tool definitions in MCP-style schema.
# `name` must exist in TOOL_REGISTRY.
LOCAL_TOOL_DEFINITIONS = [
    {
        "name": "python_tool",
        "description": (
            "Run Python code in a sandboxed container. "
            'Use this tool only with a JSON object of the form {"code": "..."} where '
            "the code value is a single Python script string. Call the tool name exactly "
            'as "python_tool".'
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute.",
                }
            },
            "required": ["code"],
            "additionalProperties": False,
        },
        "execution": {
            "mount_workspace": True,
        },
    },
]

TOOL_CALLS_COLLAPSED_BY_DEFAULT = True

# Google Search tool configuration (Google Custom Search JSON API)
# Set these environment variables before starting the app:
# export GOOGLE_SEARCH_API_KEY="..."
# export GOOGLE_SEARCH_CX="..."

# Models that should receive tool definitions (local + MCP).
# Use ["*"] to allow tools for any configured model.
TOOL_MODELS = ["nemotron-cascade-2:latest", "gpt-oss:latest"]
#
# If empty, no models are allowed to use tools.
# TOOL_MODELS: list = []

# TOOL_CALLS_COLLAPSED_BY_DEFAULT = True
# # MCP server integration (remote JSON-RPC over HTTP)
# # Tools are loaded from MCP `tools/list` and executed via MCP `tools/call`.
# MCP_SERVER_URL = "http://127.0.0.1:5000/mcp"
# MCP_AUTH_TOKEN = "your-very-secret-token"  # Set bearer token / OAuth access token when required.
# MCP_TIMEOUT_SECONDS = 20.0
# MCP_TOOLS_CACHE_SECONDS = 60.0
# # Show persisted tool calls in dialog history.


# Optional hosted MCP example:
# MCP_SERVER_URL = "https://mcp.context7.com/mcp"
# MCP_AUTH_TOKEN = "ctx7sk-..."
