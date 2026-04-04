import json
from typing import TypeVar
from urllib.parse import quote

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


async def require_user_id_json(
    request: Request,
    message: str = "Not authenticated",
    status_code: int = 401,
) -> int:
    user_id_or_response = await get_user_id_or_json_error(
        request=request,
        message=message,
        status_code=status_code,
    )
    if isinstance(user_id_or_response, JSONResponse):
        raise exceptions_validation.JSONError(message, status_code=status_code)
    return user_id_or_response


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


def build_login_redirect_target(next_path: str, *, reason: str | None = None) -> str:
    query_parts: list[str] = []
    if next_path and next_path != "/":
        query_parts.append(f"next={quote(next_path, safe='/?=&')}")
    if reason:
        query_parts.append(f"reason={quote(reason, safe='')}")
    if not query_parts:
        return "/user/login"
    return f"/user/login?{'&'.join(query_parts)}"


def json_auth_error(
    message: str,
    *,
    redirect_to: str,
    status_code: int = 401,
    reason: str = "auth_required",
    **extra,
):
    return json_error(
        message,
        status_code=status_code,
        redirect=build_login_redirect_target(redirect_to, reason=reason),
        **extra,
    )


def json_error_with_login_redirect(
    error: exceptions_validation.JSONError,
    *,
    redirect_to: str,
    reason: str = "auth_required",
    **extra,
):
    if error.status_code != 401:
        return json_error(str(error), status_code=error.status_code, **extra)
    return json_auth_error(
        str(error),
        redirect_to=redirect_to,
        status_code=error.status_code,
        reason=reason,
        **extra,
    )


def json_error(message: str, status_code: int = 400, **extra):
    return JSONResponse({"error": True, "message": message, **extra}, status_code=status_code)


def json_success(status_code: int = 200, **extra):
    return JSONResponse({"error": False, **extra}, status_code=status_code)
