from contextlib import asynccontextmanager
from starlette.applications import Starlette
from chat_client.core.exceptions import exception_callbacks
from chat_client.core.middleware import middleware
import logging
from chat_client import __version__, __program__
import data.config as config
from chat_client.core.templates import get_static_files
from chat_client.core.logging import setup_logging
from chat_client.routes import build_routes

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


app = Starlette(
    debug=False,
    routes=build_routes(static_files),
    lifespan=lifespan,
    middleware=middleware,
    exception_handlers=exception_callbacks,
)
