from starlette.requests import Request
from starlette.responses import RedirectResponse

from chat_client.core import exceptions_validation
from chat_client.core.http import get_user_id_or_redirect, json_error, json_success, require_user_id_json
from chat_client.core.templates import get_templates
from chat_client.repositories import chat_repository

templates = get_templates()


async def list_dialogs_json(request: Request):
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


async def list_dialogs(request: Request, *, get_context_fn):
    user_id_or_response = await get_user_id_or_redirect(request, notice="You must be logged in to view your profile")
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response

    context = {
        "request": request,
        "title": "Search dialogs",
    }
    context = await get_context_fn(request, context)
    return templates.TemplateResponse("users/dialogs.html", context)
