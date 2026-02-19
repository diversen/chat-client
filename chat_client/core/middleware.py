"""
Middleware for the application
"""

import json
from base64 import b64decode, b64encode

from starlette.middleware import Middleware

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from itsdangerous import BadSignature, TimestampSigner

# from starlette.middleware.cors import CORSMiddleware
# from starlette.middleware.gzip import GZipMiddleware
# NOTE: GZIP cannot be used with streaming responses
from starlette.responses import JSONResponse
from starlette.requests import Request
import data.config as config
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


class SessionMiddlewareNoResignUnlessChanged:
    """
    Session middleware that only emits Set-Cookie when session content changes.
    This avoids stale concurrent responses overwriting a fresher auth session cookie.
    """

    def __init__(
        self,
        app,
        secret_key: str,
        session_cookie: str = "session",
        max_age: int | None = 14 * 24 * 60 * 60,
        path: str = "/",
        same_site: str = "lax",
        https_only: bool = False,
        domain: str | None = None,
    ):
        self.app = app
        self.signer = TimestampSigner(str(secret_key))
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.path = path
        self.security_flags = "httponly; samesite=" + same_site
        if https_only:
            self.security_flags += "; secure"
        if domain is not None:
            self.security_flags += f"; domain={domain}"

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        initial_session_was_empty = True
        initial_session_data: dict = {}

        if self.session_cookie in connection.cookies:
            cookie_data = connection.cookies[self.session_cookie].encode("utf-8")
            try:
                cookie_data = self.signer.unsign(cookie_data, max_age=self.max_age)
                initial_session_data = json.loads(b64decode(cookie_data))
                scope["session"] = dict(initial_session_data)
                initial_session_was_empty = False
            except BadSignature:
                scope["session"] = {}
        else:
            scope["session"] = {}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                current_session_data = dict(scope["session"])
                session_changed = current_session_data != initial_session_data

                if current_session_data and session_changed:
                    data = b64encode(json.dumps(current_session_data).encode("utf-8"))
                    data = self.signer.sign(data)
                    header_value = "{session_cookie}={data}; path={path}; {max_age}{security_flags}".format(
                        session_cookie=self.session_cookie,
                        data=data.decode("utf-8"),
                        path=self.path,
                        max_age=f"Max-Age={self.max_age}; " if self.max_age else "",
                        security_flags=self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
                elif not current_session_data and not initial_session_was_empty:
                    header_value = "{session_cookie}={data}; path={path}; {expires}{security_flags}".format(
                        session_cookie=self.session_cookie,
                        data="null",
                        path=self.path,
                        expires="expires=Thu, 01 Jan 1970 00:00:00 GMT; ",
                        security_flags=self.security_flags,
                    )
                    headers.append("Set-Cookie", header_value)
            await send(message)

        await self.app(scope, receive, send_wrapper)


max_age = getattr(config, "SESSION_MAX_AGE", 14 * 24 * 60 * 60)  # 14 days default
session_cookie = getattr(config, "SESSION_COOKIE", "chat_client_session")
session_middleware = Middleware(
    SessionMiddlewareNoResignUnlessChanged,
    secret_key=getattr(config, "SESSION_SECRET_KEY", "SECRET_KEY"),
    session_cookie=session_cookie,
    https_only=getattr(config, "SESSION_HTTPS_ONLY", True),
    max_age=max_age,
    same_site="lax",
)


no_cache_middlewares = Middleware(NoCacheMiddleware)
request_max_size = getattr(config, "REQUEST_MAX_SIZE", 10 * 1024 * 1024)  # 10 MB default
limit_request_size_middlewares = Middleware(LimitRequestSizeMiddleware, max_size=request_max_size)

middleware = []
middleware.append(no_cache_middlewares)
middleware.append(session_middleware)
middleware.append(limit_request_size_middlewares)

# gzip won't work with streaming responses
# middleware.append(Middleware(GZipMiddleware, minimum_size=1000, compresslevel=9))
