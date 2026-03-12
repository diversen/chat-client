"""
Error endpoints.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
import logging
from logging import Logger

log: Logger = logging.getLogger(__name__)


async def error_log_post(request: Request):
    """
    Log posted json data
    """

    try:
        data = await request.json()
        log.error(data)
    except Exception:
        try:
            log.error("No json data in request")
        except Exception:
            pass
    return JSONResponse({"status": "received"}, status_code=200)
