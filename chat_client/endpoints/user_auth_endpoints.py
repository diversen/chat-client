import io
import logging
import random
import string

from captcha.image import ImageCaptcha
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from chat_client.core import exceptions_validation, flash, user_session
from chat_client.core.http import json_error, json_success, json_validation_error
from chat_client.core.templates import get_templates, render_template
from chat_client.repositories import user_repository

logger: logging.Logger = logging.getLogger(__name__)
templates = get_templates()


def _get_safe_next_path(value: str | None, default: str = "/") -> str:
    candidate = str(value or "").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return default
    return candidate


def _generate_captcha_text(length: int = 4) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=length))


async def signup_page(request: Request):
    return await render_template(
        templates,
        request,
        "users/signup.html",
        {
        "title": "Sign up",
        },
    )


async def signup(request: Request):
    try:
        user_row = await user_repository.create_user(request)
        user_session.set_session_variable(request, "user_id", user_row["user_id"])
        return json_success(
            message=(
                "Your account was created successfully. "
                "Check your email in order to verify your account. After verification you may login."
            )
        )
    except exceptions_validation.UserValidate as e:
        return json_validation_error(e)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def verify_page(request: Request):
    token = request.query_params.get("token")
    return await render_template(
        templates,
        request,
        "users/verify.html",
        {
        "title": "Verify account",
        "token": token,
        },
    )


async def verify(request: Request):
    try:
        await user_repository.verify_user(request)
        return json_success(message="Your account has been verified successfully")
    except exceptions_validation.UserValidate as e:
        return json_validation_error(e)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def login_page(request: Request):
    next_path = _get_safe_next_path(request.query_params.get("next"))
    if request.query_params.get("reason") == "auth_required" and not await user_session.is_logged_in(request):
        flash.set_notice(request, "You are not logged in. Please log in.")

    return await render_template(
        templates,
        request,
        "users/login.html",
        {
        "title": "Login",
        "next_path": next_path,
        },
    )


async def login(request: Request):
    try:
        payload = await request.json()
        login_user = await user_repository.login_user(request)
        user_session.set_session_variable(request, "user_id", login_user["user_id"])
        next_path = _get_safe_next_path(payload.get("next"))
        return json_success(redirect=next_path, message="You are now logged in")
    except exceptions_validation.UserValidate as e:
        return json_validation_error(e)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def get_captcha(request: Request):
    captcha_text = _generate_captcha_text()
    request.session["captcha"] = captcha_text

    image = ImageCaptcha(width=200, height=60)
    captcha_image = image.generate(captcha_text)
    img_bytes = io.BytesIO()
    img_bytes.write(captcha_image.getvalue())
    img_bytes.seek(0)

    return Response(content=img_bytes.getvalue(), media_type="image/png")


async def logout_page(request: Request):
    if request.query_params.get("logout"):
        await user_session.clear_user_session(request)
        flash.set_success(request, "You are logged out")
        return RedirectResponse(url="/user/login")

    if request.query_params.get("logout_all"):
        await user_session.clear_user_session(request, all=True)
        flash.set_success(request, "You are logged out of all your devices")
        return RedirectResponse(url="/user/login")

    return await render_template(
        templates,
        request,
        "users/logout.html",
        {
        "title": "Logout",
        },
    )


async def reset_password_page(request: Request):
    return await render_template(
        templates,
        request,
        "users/reset_password.html",
        {
        "title": "Reset password",
        },
    )


async def reset_password(request: Request):
    try:
        await user_repository.reset_password(request)
        return json_success(
            message=(
                "A password reset email has been sent. "
                "Check your email and click the link in the email to reset your password. "
                "Then you can login with your new password."
            )
        )
    except exceptions_validation.UserValidate as e:
        return json_validation_error(e)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def new_password_page(request: Request):
    token = request.query_params.get("token")
    return await render_template(
        templates,
        request,
        "users/new_password.html",
        {
        "title": "New password",
        "token": token,
        },
    )


async def new_password(request: Request):
    try:
        await user_repository.new_password(request)
        return json_success(message="Password has been updated. You can now login.")
    except exceptions_validation.UserValidate as e:
        return json_validation_error(e)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")
