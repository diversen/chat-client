import logging

from starlette.requests import Request
from starlette.responses import RedirectResponse

from chat_client.core import exceptions_validation
from chat_client.core.http import get_user_id_or_redirect, json_error_from_exception, json_success, require_user_id_json
from chat_client.core.templates import get_templates, render_template
from chat_client.repositories import chat_repository

logger: logging.Logger = logging.getLogger(__name__)
templates = get_templates()


async def usage_page(request: Request):
    user_id_or_response = await get_user_id_or_redirect(request, notice="You must be logged in to view usage")
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response

    totals = await chat_repository.get_user_usage_totals(user_id)
    return await render_template(
        templates,
        request,
        "users/usage.html",
        {
            "title": "Usage",
            "usage_totals": totals,
        },
    )


async def get_usage(request: Request):
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
        totals = await chat_repository.get_user_usage_totals(user_id)
        dialogs_info = await chat_repository.get_user_usage_by_dialog_info(user_id, current_page=current_page)
        return json_success(totals=totals, dialogs_info=dialogs_info, dialogs=dialogs_info["dialogs"])
    except exceptions_validation.JSONError as error:
        return json_error_from_exception(error)
