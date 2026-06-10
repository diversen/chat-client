from contextlib import asynccontextmanager
import json
from starlette.applications import Starlette
from chat_client.core.exceptions import exception_callbacks
from chat_client.core.middleware import middleware
from chat_client.core import model_capabilities
from chat_client.core import tool_executor
import logging
from chat_client import __version__, __program__
import data.config as config
from chat_client.core.templates import get_static_files
from chat_client.core.logging import setup_logging
from chat_client.routes import build_routes
from chat_client.core import config_utils
from chat_client.core import chat_service

# Setup logging
log_level = config.LOG_LEVEL
setup_logging(log_level)
logger: logging.Logger = logging.getLogger(__name__)
logger.info(f"Starting {__program__} ({__version__})")


static_files = get_static_files()
MODELS = config_utils.resolve_models(getattr(config, "MODELS", {}), getattr(config, "PROVIDERS", {}))
PROVIDERS = getattr(config, "PROVIDERS", {})
VISION_MODELS = getattr(config, "VISION_MODELS", [])
TOOL_MODELS = getattr(config, "TOOL_MODELS", [])
TOOL_REGISTRY = getattr(config, "TOOL_REGISTRY", {})
LOCAL_TOOL_DEFINITIONS = getattr(config, "LOCAL_TOOL_DEFINITIONS", [])
MCP_SERVER_URL = getattr(config, "MCP_SERVER_URL", "")
MCP_AUTH_TOKEN = getattr(config, "MCP_AUTH_TOKEN", "")
SYSTEM_MESSAGE_DENYLIST = getattr(config, "SYSTEM_MESSAGE_DENYLIST", [])


def _resolve_provider_info(model: str) -> dict:
    return chat_service.resolve_provider_info(model, MODELS, PROVIDERS)


def _model_capabilities_cache_token() -> dict:
    return {
        "providers": PROVIDERS,
        "models": MODELS,
        "vision_models": VISION_MODELS,
        "tool_models": TOOL_MODELS,
        "system_message_denylist": SYSTEM_MESSAGE_DENYLIST,
    }


@asynccontextmanager
async def lifespan(app):
    logger.info(
        "Tools enabled at startup:\n%s",
        json.dumps(
            tool_executor.build_startup_tool_summary(
                tool_registry=TOOL_REGISTRY,
                local_tool_definitions=LOCAL_TOOL_DEFINITIONS,
                mcp_server_url=MCP_SERVER_URL,
                mcp_auth_token=MCP_AUTH_TOKEN,
                tool_models=TOOL_MODELS,
            ),
            indent=2,
            sort_keys=True,
        ),
    )
    model_capabilities.warm_and_log_model_capabilities(
        logger=logger,
        models=MODELS,
        vision_models=VISION_MODELS,
        tool_models=TOOL_MODELS,
        system_message_denylist=SYSTEM_MESSAGE_DENYLIST,
        provider_info_resolver=_resolve_provider_info,
        cache_token=_model_capabilities_cache_token(),
    )
    logger.info("Accepting incoming requests")
    yield
    logger.info("End of lifespan")


app = Starlette(
    debug=False,
    routes=build_routes(static_files),
    lifespan=lifespan,
    middleware=middleware,
    exception_handlers=exception_callbacks,
)
