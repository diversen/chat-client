from chat_client.core import base_context
import logging
from starlette.responses import JSONResponse
from chat_client.core.templates import get_templates

logger: logging.Logger = logging.getLogger(__name__)


templates = get_templates()


# Generate a UserValidate Exception
class UserValidate(Exception):
    pass


class JSONError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class NotAuthorized(Exception):
    pass


class NotFound(Exception):
    pass


async def _500(request, exc):
    message = str(exc)
    error_code = 500
    if isinstance(exc, UserValidate):
        error_code = "400 Bad Request"

    if isinstance(exc, NotAuthorized):
        error_code = "401 Unauthorized"

    context = {
        "request": request,
        "title": "Error Page",
        "message": message,
        "error_code": error_code,
    }

    context = await base_context.get_context(request, context)

    return templates.TemplateResponse("error.html", context, status_code=500)


async def _400(request, exc):
    error_code = "404 Not Found"
    context = {
        "request": request,
        "title": "Error Page",
        "message": "The page you are looking for does not exist",
        "error_code": error_code,
    }

    context = await base_context.get_context(request, context)

    return templates.TemplateResponse("error.html", context, status_code=404)


async def _json_error_handler(request, exc):
    status_code = getattr(exc, "status_code", 400)
    return JSONResponse({"error": True, "message": str(exc)}, status_code=status_code)


exception_callbacks = {
    404: _400,  # Catch 404 errors
    500: _500,  # Catch 500 errors
    JSONError: _json_error_handler,  # Catch JSON errors
    Exception: _500,  # Catch all unhandled exceptions
}
