import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from chat_client.core import exceptions_validation, flash, user_session

T = TypeVar("T", bound=BaseModel)


async def parse_json_payload(request: Request, model_class: type[T]) -> T:
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise exceptions_validation.JSONError("Invalid JSON body", status_code=400)

    try:
        return model_class.model_validate(payload)
    except ValidationError as exc:
        error_msg = exc.errors()[0].get("msg", "Invalid request body")
        raise exceptions_validation.JSONError(error_msg, status_code=400)


async def get_user_id_or_json_error(
    request: Request,
    message: str = "Not authenticated",
    status_code: int = 401,
):
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        return JSONResponse({"error": True, "message": message}, status_code=status_code)
    return user_id


async def get_user_id_or_redirect(
    request: Request,
    notice: str | None = None,
    login_path: str = "/user/login",
):
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        if notice:
            flash.set_notice(request, notice)
        return RedirectResponse(url=login_path)
    return user_id


def json_error(message: str, status_code: int = 200, **extra):
    return JSONResponse({"error": True, "message": message, **extra}, status_code=status_code)


def json_success(status_code: int = 200, **extra):
    return JSONResponse({"error": False, **extra}, status_code=status_code)
