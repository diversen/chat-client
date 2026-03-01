import logging
from pathlib import Path
from chat_client.core.api_utils import get_provider_models
from chat_client.tools.python_tool import python as python_tool
from chat_client.tools.google_search_tool import google_search


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

# Add all ollama models to the list of models
if "ollama" in PROVIDERS:
    try:
        ollama_models = get_provider_models(PROVIDERS["ollama"])
        for ollama_model in ollama_models:
            MODELS[ollama_model] = "ollama"
    except Exception as e:
        print(f"Error getting ollama provided models: {e}")
        print("You can try to fix this by:")
        print("a) Install and run the ollama server")
        print("b) Edit the config.py file and remove the provider ollama")
        exit()

# Enable vision models (models that can process both text and images)
VISION_MODELS = []

# System models are models that are capable of injecting initial system instruction into the model template.
# Not all models supports this, so we need to specify which models that should receive system instructions.
SYSTEM_MESSAGE_MODELS: list = []

# Optional local tool registry (preferred over MCP when configured).
# Functions must be callables that accept keyword arguments.
def ping():
    return "Is alive!"


TOOL_REGISTRY = {
    "ping": ping,
    "python": python_tool,
    "google_search": google_search,
}

# Optional explicit local tool definitions in MCP-style schema.
# `name` must exist in TOOL_REGISTRY.
LOCAL_TOOL_DEFINITIONS = [
    {
        "name": "ping",
        "description": "Simple ping tool to check if the tool system is working",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "python",
        "description": "Execute Python code and return output/result.",
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
    },
    {
        "name": "google_search",
        "description": "Search Google and return compact JSON results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (1-10).",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
]

# Google Search tool configuration (Google Custom Search JSON API)
# Set these environment variables before starting the app:
# export GOOGLE_SEARCH_API_KEY="..."
# export GOOGLE_SEARCH_CX="..."

# Models that should receive tool definitions (local + MCP).
# TOOL_MODELS = ["gpt-40-mini"]
#
# If empty and either
# TOOL_REGISTRY or MCP is configured, all configured MODELS are allowed.
TOOL_MODELS: list = []

SHOW_TOOL_CALLS = True
# MCP server integration (remote JSON-RPC over HTTP)
# Tools are loaded from MCP `tools/list` and executed via MCP `tools/call`.
MCP_SERVER_URL = "http://127.0.0.1:5000/mcp"
MCP_AUTH_TOKEN = "your-very-secret-token"  # Set bearer token / OAuth access token when required.
MCP_TIMEOUT_SECONDS = 20.0
MCP_TOOLS_CACHE_SECONDS = 60.0
# Show persisted tool calls in dialog history.


# Optional hosted MCP example:
# MCP_SERVER_URL = "https://mcp.context7.com/mcp"
# MCP_AUTH_TOKEN = "ctx7sk-..."
