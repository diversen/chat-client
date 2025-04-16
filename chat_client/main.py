from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette.routing import Mount
from chat_client.endpoints.endpoints_chat import routes_chat
from chat_client.endpoints.endpoints_user import routes_user
from chat_client.endpoints.endpoints_error import routes_error
from chat_client.core.exceptions import exception_callbacks
from chat_client.core.middleware import middleware
import logging
from chat_client import __version__, __program__
import config
from chat_client.core.templates import get_static_files
from chat_client.core.logging import setup_logging

# Setup logging
log_level = config.LOG_LEVEL
setup_logging(log_level)
logger: logging.Logger = logging.getLogger(__name__)
logger.info(f"Starting {__program__} ({__version__})")


static_files = get_static_files()


@asynccontextmanager
async def lifespan(app):
    logger.info("Accepting incoming requests")
    yield
    logger.info("End of lifespan")


all_routes = [
    Mount("/static", app=static_files, name="static"),
]

all_routes.extend(routes_user)
all_routes.extend(routes_chat)
all_routes.extend(routes_error)

app = Starlette(
    debug=False,
    routes=all_routes,
    lifespan=lifespan,
    middleware=middleware,
    exception_handlers=exception_callbacks,
)
