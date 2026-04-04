from starlette.requests import Request

from chat_client.core.base_context import get_context
from chat_client.endpoints import user_auth_endpoints, user_dialog_endpoints, user_profile_endpoints


async def signup_get(request: Request):
    return await user_auth_endpoints.signup_get(request, get_context_fn=get_context)


async def signup_post(request: Request):
    return await user_auth_endpoints.signup_post(request)


async def verify_get(request: Request):
    return await user_auth_endpoints.verify_get(request, get_context_fn=get_context)


async def verify_post(request: Request):
    return await user_auth_endpoints.verify_post(request)


async def login_get(request: Request):
    return await user_auth_endpoints.login_get(request, get_context_fn=get_context)


async def login_post(request: Request):
    return await user_auth_endpoints.login_post(request)


async def captcha_image(request: Request):
    return await user_auth_endpoints.captcha_image(request)


async def logout_get(request: Request):
    return await user_auth_endpoints.logout_get(request, get_context_fn=get_context)


async def reset_password_get(request: Request):
    return await user_auth_endpoints.reset_password_get(request, get_context_fn=get_context)


async def reset_password_post(request: Request):
    return await user_auth_endpoints.reset_password_post(request)


async def new_password_get(request: Request):
    return await user_auth_endpoints.new_password_get(request, get_context_fn=get_context)


async def new_password_post(request: Request):
    return await user_auth_endpoints.new_password_post(request)


async def list_dialogs_json(request: Request):
    return await user_dialog_endpoints.list_dialogs_json(request)


async def list_dialogs(request: Request):
    return await user_dialog_endpoints.list_dialogs(request, get_context_fn=get_context)


async def profile(request: Request):
    return await user_profile_endpoints.profile(request, get_context_fn=get_context)


async def profile_post(request: Request):
    return await user_profile_endpoints.profile_post(request)
