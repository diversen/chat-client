"""Starlette routes for Prompt CRUD."""

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse
from chat_client.core.templates import get_templates
from chat_client.core.base_context import get_context

# from chat_client.core.exceptions import UserValidate
from chat_client.core import exceptions_validation
from chat_client.repositories import prompt_repository
from chat_client.core import flash
from chat_client.core.http import (
    require_user_id_json,
    get_user_id_or_redirect,
    parse_json_payload,
    json_error,
    json_success,
)
from chat_client.schemas.prompt import PromptUpsertRequest

templates = get_templates()


async def prompt_list_get(request: Request):
    user_id_or_response = await get_user_id_or_redirect(request)
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response
    prompts = await prompt_repository.list_prompts(user_id)
    context = {
        "request": request,
        "title": "Your Prompts",
        "prompts": prompts,
        "logged_in": True,
    }
    context = await get_context(request, context)
    return templates.TemplateResponse("prompts/list.html", context)


async def prompt_list_json(request: Request):
    try:
        user_id = await require_user_id_json(request, message="Not authenticated")
        prompts = await prompt_repository.list_prompts(user_id)
        data = [
            {
                "prompt_id": p.prompt_id,
                "title": p.title,
                "prompt": p.prompt,
            }
            for p in prompts
        ]
        return JSONResponse({"error": False, "prompts": data})
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)


async def prompt_create_get(request: Request):
    user_id_or_response = await get_user_id_or_redirect(request)
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    context = {
        "request": request,
        "title": "Create Prompt",
        "logged_in": True,
    }
    context = await get_context(request, context)
    return templates.TemplateResponse("prompts/create.html", context)


async def prompt_create_post(request: Request):
    try:
        user_id = await require_user_id_json(request, message="Not authenticated")
        payload = await parse_json_payload(request, PromptUpsertRequest)
        result = await prompt_repository.create_prompt(user_id, payload.title, payload.prompt)
        flash.set_success(request, "Prompt created successfully")
        return json_success(prompt_id=result["prompt_id"])
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)


async def prompt_detail(request: Request):
    prompt_id = int(request.path_params["prompt_id"])
    user_id_or_response = await get_user_id_or_redirect(request)
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response
    try:
        prompt = await prompt_repository.get_prompt(user_id, prompt_id)
    except exceptions_validation.UserValidate:
        return RedirectResponse("/prompt")
    context = {
        "request": request,
        "title": prompt.title,
        "prompt": prompt,
        "logged_in": True,
    }
    context = await get_context(request, context)
    return templates.TemplateResponse("prompts/detail.html", context)


async def prompt_detail_json(request: Request):
    try:
        prompt_id = int(request.path_params["prompt_id"])
        user_id = await require_user_id_json(request, message="Not authenticated")
        prompt = await prompt_repository.get_prompt(user_id, prompt_id)
    except exceptions_validation.UserValidate:
        return JSONResponse({"error": True, "message": "Prompt not found"}, status_code=404)
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    data = {
        "prompt_id": prompt.prompt_id,
        "title": prompt.title,
        "prompt": prompt.prompt,
    }
    return JSONResponse({"error": False, "prompt": data})


async def prompt_edit_get(request: Request):
    prompt_id = int(request.path_params["prompt_id"])
    user_id_or_response = await get_user_id_or_redirect(request)
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response
    try:
        prompt = await prompt_repository.get_prompt(user_id, prompt_id)
    except exceptions_validation.UserValidate:
        return RedirectResponse("/prompt")
    context = {
        "request": request,
        "title": f"Edit {prompt.title}",
        "prompt": prompt,
        "logged_in": True,
    }
    context = await get_context(request, context)
    return templates.TemplateResponse("prompts/edit.html", context)


async def prompt_edit_post(request: Request):

    prompt_id = int(request.path_params["prompt_id"])
    user_id_or_response = await get_user_id_or_redirect(request)
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response

    prompt = await prompt_repository.get_prompt(user_id, prompt_id)
    if not prompt:
        return json_error("Prompt not found", status_code=404)

    try:
        payload = await parse_json_payload(request, PromptUpsertRequest)
        await prompt_repository.update_prompt(user_id, prompt_id, payload.title, payload.prompt)
        flash.set_success(request, "Prompt updated successfully")
        return json_success()
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)


async def prompt_delete_post(request: Request):
    prompt_id = int(request.path_params["prompt_id"])
    user_id_or_response = await get_user_id_or_redirect(request)
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response
    prompt = await prompt_repository.get_prompt(user_id, prompt_id)

    if not prompt:
        return json_error("Prompt not found", status_code=404)
    try:
        await prompt_repository.delete_prompt(user_id, prompt_id)
        flash.set_success(request, "Prompt deleted successfully")
        return json_success()
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)


routes_prompt = [
    Route("/prompt", prompt_list_get, methods=["GET"]),
    Route("/prompt/json", prompt_list_json, methods=["GET"]),
    Route("/prompt/create", prompt_create_get, methods=["GET"]),
    Route("/prompt/create", prompt_create_post, methods=["POST"]),
    Route("/prompt/{prompt_id:int}", prompt_detail, methods=["GET"]),
    Route("/prompt/{prompt_id:int}/edit", prompt_edit_get, methods=["GET"]),
    Route("/prompt/{prompt_id:int}/edit", prompt_edit_post, methods=["POST"]),
    Route("/prompt/{prompt_id:int}/delete", prompt_delete_post, methods=["POST"]),
    Route("/prompt/{prompt_id:int}/json", prompt_detail_json, methods=["GET"]),
]
