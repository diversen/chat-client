from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse, RedirectResponse
import logging
from starlette.responses import Response
import random
from captcha.image import ImageCaptcha
import string
import io
from chat_client.repositories import chat_repository, user_repository
from chat_client.core import flash
from chat_client.core.exceptions import UserValidate
from chat_client.core import user_session
from chat_client.core.templates import get_templates
from chat_client.core.base_context import get_context


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

        return JSONResponse({"error": False, "message": "Your account has been created"})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception as e:
        logger.exception(e)
        return JSONResponse({"error": True, "message": "An unexpected error occurred"})


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
        return JSONResponse({"error": False})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception as e:
        logger.exception(e)
        return JSONResponse({"error": True, "message": "An unexpected error occurred"})


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
        return JSONResponse({"error": False})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception as e:
        logger.exception(e)
        return JSONResponse({"error": True, "message": "An unexpected error occurred"})


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
        return JSONResponse({"error": False, "message": "A password reset email has been sent."})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception as e:
        logger.exception(e)
        return JSONResponse({"error": True, "message": "An unexpected error occurred"})


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
        return JSONResponse({"error": False, "message": "Password reset email sent"})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception as e:
        logger.exception(e)
        return JSONResponse({"error": True, "message": "An unexpected error occurred"})


async def list_dialogs_json(request: Request):
    """
    Get user dialogs from database
    Endpoint /user/dialogs
    """

    dialogs_info = await chat_repository.get_dialogs_info(request)
    return JSONResponse({"error": False, "dialogs_info": dialogs_info})


async def list_dialogs(request: Request):
    """
    Get user dialogs from database
    Endpoint /user/dialogs
    """

    user_id = await user_session.is_logged_in(request)
    if not user_id:
        flash.set_notice(request, "You must be logged in to view your profile")
        return RedirectResponse(url="/user/login")

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
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        flash.set_notice(request, "You must be logged in to view your profile")
        return RedirectResponse(url="/user/login")

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
        return JSONResponse({"error": False, "message": "Profile updated"})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception as e:
        logger.exception(e)
        return JSONResponse({"error": True, "message": "An unexpected error occurred"})


async def is_logged_in(request: Request):
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        flash.set_notice(request, "You are logged out. Please login again.")
        return JSONResponse({"error": True, "redirect": "/user/login"})

    return JSONResponse({"error": False, "message": "You are logged in"})


routes_user: list = [
    Route("/captcha", captcha_, methods=["GET"]),
    Route("/user/signup", signup_get, methods=["GET"]),
    Route("/user/signup", signup_post, methods=["POST"]),
    Route("/user/login", login_get, methods=["GET"]),
    Route("/user/login", login_post, methods=["POST"]),
    Route("/user/verify", verify_get, methods=["GET"]),
    Route("/user/verify", verify_post, methods=["POST"]),
    Route("/user/logout", logout_get, methods=["GET"]),
    Route("/user/reset", reset_password_get, methods=["GET"]),
    Route("/user/reset", reset_password_post, methods=["POST"]),
    Route("/user/new-password", new_password_get, methods=["GET"]),
    Route("/user/new-password", new_password_post, methods=["POST"]),
    Route("/user/dialogs", list_dialogs, methods=["GET"]),
    Route("/user/dialogs/json", list_dialogs_json, methods=["GET"]),
    Route("/user/profile", profile, methods=["GET"]),
    Route("/user/profile", profile_post, methods=["POST"]),
    Route("/user/is-logged-in", is_logged_in, methods=["GET"]),
]
