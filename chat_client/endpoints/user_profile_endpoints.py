import logging

from starlette.requests import Request
from starlette.responses import RedirectResponse

from chat_client.core import exceptions_validation
from chat_client.core.http import get_user_id_or_redirect, json_error, json_error_with_login_redirect, json_success, require_user_id_json
from chat_client.core.templates import get_templates
from chat_client.repositories import user_repository

logger: logging.Logger = logging.getLogger(__name__)
templates = get_templates()


async def profile(request: Request, *, get_context_fn):
    user_id_or_response = await get_user_id_or_redirect(request, notice="You must be logged in to view your profile")
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response

    profile_data = await user_repository.get_profile(user_id)
    context = {
        "request": request,
        "title": "Profile",
        "profile": profile_data,
    }
    context = await get_context_fn(request, context)
    return templates.TemplateResponse("users/profile.html", context)


async def profile_post(request: Request):
    try:
        await require_user_id_json(request, message="You must be logged in to update your profile")
        await user_repository.update_profile(request)
        return json_success(message="Profile updated successfully")
    except exceptions_validation.JSONError as e:
        return json_error_with_login_redirect(e, redirect_to="/user/profile")
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception as e:
        logger.exception(e)
        return json_error("An unexpected error occurred")
