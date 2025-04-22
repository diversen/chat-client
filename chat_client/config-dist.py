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


# Default model
DEFAULT_MODEL = "deepseek-r1:14b"

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

# Session HTTPS only
SESSION_HTTPS_ONLY = False  # Set to True if using HTTPS

# Use mathjax for rendering math
USE_KATEX = False

# Tools that can be called from the frontend
#
# Only available tool is python execution.
# Very simple PYTHON_EXEC_TEMPLATE but unasafe
# PYTHON_EXEC_TEMPLATE = "python3 {filename}"
# A docker image that can be used to execute python code in a secure environment
# See: https://github.com/diversen/secure-python
#
# PYTHON_EXEC_TEMPLATE = (
#     "docker run --network none --init --rm --memory=256m --memory-swap=256m "
#     "--cpus='0.5' --ulimit nproc=2000:2000 --ulimit stack=67108864 "
#     "-v {filename}:/sandbox/script.py secure-python script.py"
# )

# TOOLS_CALLBACK = {
#     # this tool may be called on /tools/python
#     # The tool will call the function execute in the module ollama_client.tools.python_exec
#     # The result will be added to the dialog
#     # Uncomment in order to run python code
#     "python": {
#         "module": "chat_client.tools.python_exec",
#         "def": "execute",
#     }
# }

PROVIDERS = {
    # "openai": {
    #     "base_url": "https://api.openai.com/v1",
    #     "api_key": "API_KEY",
    # },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    },
}


MODELS = {
    # "gpt-4o-mini": "openai",
}

# Add all ollama models to the list of models
try:
    ollama_models = get_provider_models(PROVIDERS["ollama"])
    for ollama_model in ollama_models:
        MODELS[ollama_model] = "ollama"
except Exception as e:
    print(f"Error getting ollama provided models: {e}")
    print("You can try to fix this by:")
    print("a) Install and run the ollama server")
    print("b) Edit the config.py file and remove the provier ollama")
    exit()


TOOL_MODELS = ["gpt-40-mini"]


# # Model tools configuration

# # In my expirence most ollama models are not very good at handling tools
# # And also: If using tools with a model you loss the ability to stream the response
# # The response will be returned as a single response
# # But anyway here is an example of how to use tools with models

# def get_current_time(timezone: str) -> str:

#     import datetime
#     import pytz

#     try:
#         now = datetime.datetime.now(pytz.timezone(timezone))
#         return f"The current time in {timezone} is {now.strftime('%H:%M:%S')}."
#     except Exception:
#         return f"Invalid timezone: {timezone}"


# # Tool registry
# TOOL_REGISTRY = {"get_current_time": get_current_time}

# # Tools
# TOOLS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "get_current_time",
#             "description": "Returns the current time in a specific timezone",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "timezone": {
#                         "type": "string",
#                         "description": "Timezone in IANA format, e.g. 'Europe/Copenhagen'",
#                     }
#                 },
#                 "required": ["timezone"],
#             },
#         },
#     }
# ]
