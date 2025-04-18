"""
Middleware for the application
"""

from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

# from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
import config
import logging

logger: logging.Logger = logging.getLogger(__name__)


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path

        # cache static files for 1 year. There are versioning on the static files
        # so they will be reloaded when version is changed
        if path.startswith("/static"):
            response.headers["Cache-Control"] = "public, max-age=31536000"
            return response

        # ignore_paths = ["/"]  # chat page
        # for ignore_path in ignore_paths:
        #     if path == ignore_path:
        #         # Default cache. No cache directives are sent, so the browser
        #         # will cache the response as it sees fit.
        #         return response

        # Ensure no cache. Do not store any part of the response in the cache
        # Will force the browser to always request a new version of the page
        response.headers["Cache-Control"] = "no-store"
        return response


class LimitRequestSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        request_body = await request.body()
        if len(request_body) > self.max_size:
            return JSONResponse({"error": True, "message": "Request body too large"}, status_code=413)
        return await call_next(request)

MAX_AGE = 14 * 24 * 60 * 60  # 14 days
session_middleware = Middleware(
    SessionMiddleware,
    secret_key=getattr(config, "SESSION_SECRET_KEY", "SECRET_KEY"),
    https_only=getattr(config, "SESSION_HTTPS_ONLY", True),
    max_age=getattr(config, "SESSION_MAX_AGE", MAX_AGE),
    same_site="lax",
)


no_cache_middlewares = Middleware(NoCacheMiddleware)
limit_request_size_middlewares = Middleware(LimitRequestSizeMiddleware, max_size=100 * 1024)  # 50 KB

middleware = []
middleware.append(no_cache_middlewares)
middleware.append(session_middleware)
middleware.append(limit_request_size_middlewares)

# gzip won't work with streaming responses
# middleware.append(Middleware(GZipMiddleware, minimum_size=1000, compresslevel=9))
