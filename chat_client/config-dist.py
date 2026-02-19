import logging
from pathlib import Path
from chat_client.core.api_utils import get_provider_models


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


# Models that should receive MCP tool definitions.
# MCP_MODELS = ["gpt-40-mini"]

# MCP is disabled when MCP_MODELS is empty.
MCP_MODELS = []
# MCP server integration (remote JSON-RPC over HTTP)
# Tools are loaded from MCP `tools/list` and executed via MCP `tools/call`.
MCP_SERVER_URL = "http://127.0.0.1:5000/mcp"
MCP_AUTH_TOKEN = "your-very-secret-token"  # Set bearer token / OAuth access token when required.
MCP_TIMEOUT_SECONDS = 20.0
MCP_TOOLS_CACHE_SECONDS = 60.0

# Optional hosted MCP example:
# MCP_SERVER_URL = "https://mcp.context7.com/mcp"
# MCP_AUTH_TOKEN = "ctx7sk-..."


# In my expirence most ollama models are not very good at handling tools.
# If using tools with a model you also loss the ability to stream the response.
