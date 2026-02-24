from starlette.requests import Request
from starlette.responses import RedirectResponse
import logging
from starlette.responses import Response
import random
from captcha.image import ImageCaptcha
import string
import io
from chat_client.repositories import chat_repository, user_repository
from chat_client.core import flash

# from chat_client.core.exceptions import UserValidate
from chat_client.core import exceptions_validation
from chat_client.core import user_session
from chat_client.core.templates import get_templates
from chat_client.core.base_context import get_context
from chat_client.core.http import get_user_id_or_redirect, require_user_id_json, json_error, json_success


logger: logging.Logger = logging.getLogger(__name__)
templates = get_templates()


# set max unix time for verification
TIME_TO_VERIFY = 60 * 10


def _generate_captcha_text(length=4):
    random_chars = "".join(random.choices(string.ascii_uppercase, k=length))
    return random_chars


async def signup_get(request: Request):
    context = {
        "request": request,
        "title": "Sign up",
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("users/signup.html", context)


async def signup_post(request: Request):
    try:
        user_row = await user_repository.create_user(request)
        user_session.set_session_variable(request, "user_id", user_row["user_id"])
        flash.set_success(
            request,
            "Your account was created successfully. " "Check your email in order to verify your account. After verification you may login.",
        )

        return json_success(message="Your account has been created")
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def verify_get(request: Request):
    token = request.query_params.get("token")
    context = {
        "request": request,
        "title": "Verify account",
        "token": token,
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("users/verify.html", context)


async def verify_post(request: Request):
    try:
        await user_repository.verify_user(request)
        flash.set_success(request, "Your account has been verified successfully")
        return json_success()
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def login_get(request: Request):
    context = {
        "request": request,
        "title": "Login",
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("users/login.html", context)


async def login_post(request: Request):
    try:
        login_user = await user_repository.login_user(request)
        user_session.set_session_variable(request, "user_id", login_user["user_id"])
        flash.set_success(request, "You are now logged in")
        return json_success()
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def captcha_(request):
    captcha_text = _generate_captcha_text()
    request.session["captcha"] = captcha_text

    # Create CAPTCHA image
    image = ImageCaptcha(width=200, height=60)
    captcha_image = image.generate(captcha_text)

    # Read image bytes
    img_bytes = io.BytesIO()
    img_bytes.write(captcha_image.getvalue())
    img_bytes.seek(0)

    return Response(content=img_bytes.getvalue(), media_type="image/png")


async def logout_get(request: Request):
    # check if query param logout is present
    if request.query_params.get("logout"):
        await user_session.clear_user_session(request)
        flash.set_success(request, "You are logged out")
        return RedirectResponse(url="/user/login")

    if request.query_params.get("logout_all"):
        await user_session.clear_user_session(request, all=True)
        flash.set_success(request, "You are logged out of all your devices")
        return RedirectResponse(url="/user/login")

    # present logout template
    context = {
        "request": request,
        "title": "Logout",
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("users/logout.html", context)


async def reset_password_get(request: Request):
    context = {
        "request": request,
        "title": "Reset password",
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("users/reset_password.html", context)


async def reset_password_post(request: Request):
    try:
        await user_repository.reset_password(request)
        flash.set_success(
            request,
            "A password reset email has been sent. "
            "Check your email and click the link in the email to reset your password. "
            "Then you can login with your new password.",
        )
        return json_success(message="A password reset email has been sent.")
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def new_password_get(request: Request):
    token = request.query_params.get("token")
    context = {
        "request": request,
        "title": "New password",
        "token": token,
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("users/new_password.html", context)


async def new_password_post(request: Request):
    try:
        await user_repository.new_password(request)
        flash.set_success(request, "Password has been updated. You can now login.")
        return json_success(message="Password reset email sent")
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def list_dialogs_json(request: Request):
    """
    Get user dialogs from database
    Endpoint /user/dialogs
    """
    try:
        user_id = await require_user_id_json(
            request,
            message="It seems you have been logged out. Log in again",
            status_code=401,
        )
        page_raw = str(request.query_params.get("page", "1")).strip()
        try:
            current_page = int(page_raw)
        except ValueError:
            raise exceptions_validation.JSONError("Invalid page parameter", status_code=400)
        if current_page < 1:
            raise exceptions_validation.JSONError("Invalid page parameter", status_code=400)

        query = str(request.query_params.get("q", "")).strip()
        dialogs_info = await chat_repository.get_dialogs_info(user_id, current_page=current_page, query=query)
        return json_success(dialogs_info=dialogs_info)
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)


async def list_dialogs(request: Request):
    """
    Get user dialogs from database
    Endpoint /user/dialogs
    """

    user_id_or_response = await get_user_id_or_redirect(request, notice="You must be logged in to view your profile")
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response

    context = {
        "request": request,
        "title": "Search dialogs",
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("users/dialogs.html", context)


async def profile(request: Request):
    """
    List profile edit page
    """
    user_id_or_response = await get_user_id_or_redirect(request, notice="You must be logged in to view your profile")
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response

    profile = await user_repository.get_profile(user_id)
    context = {
        "request": request,
        "title": "Profile",
        "profile": profile,
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("users/profile.html", context)


async def profile_post(request: Request):
    try:
        await user_repository.update_profile(request)
        flash.set_success(request, "Profile updated successfully")
        return json_success()
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")


async def is_logged_in(request: Request):
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        flash.set_notice(request, "You are logged out. Please login again.")
        return json_error("You are logged out. Please login again.", redirect="/user/login")

    return json_success(message="You are logged in")
