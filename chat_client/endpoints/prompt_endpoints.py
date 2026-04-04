"""Starlette routes for Prompt CRUD."""

from starlette.requests import Request
from starlette.responses import RedirectResponse
from chat_client.core.templates import get_templates, render_template

# from chat_client.core.exceptions import UserValidate
from chat_client.core import exceptions_validation
from chat_client.repositories import prompt_repository
from chat_client.core.http import (
    get_user_id_or_redirect,
    json_error,
    json_error_from_exception,
    json_success,
    json_validation_error,
    parse_json_payload,
    require_user_id_json,
)
from chat_client.schemas.prompt import PromptUpsertRequest

templates = get_templates()


async def prompt_list_get(request: Request):
    user_id_or_response = await get_user_id_or_redirect(request)
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response
    prompts = await prompt_repository.list_prompts(user_id)
    return await render_template(
        templates,
        request,
        "prompts/list.html",
        {"title": "Your Prompts", "prompts": prompts, "logged_in": True},
    )


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
        return json_success(prompts=data)
    except exceptions_validation.JSONError as e:
        return json_error_from_exception(e, redirect_to="/prompt")


async def prompt_create_get(request: Request):
    user_id_or_response = await get_user_id_or_redirect(request)
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    return await render_template(
        templates,
        request,
        "prompts/create.html",
        {"title": "New Custom Prompt", "logged_in": True},
    )


async def prompt_create_post(request: Request):
    try:
        user_id = await require_user_id_json(request, message="Not authenticated")
        payload = await parse_json_payload(request, PromptUpsertRequest)
        result = await prompt_repository.create_prompt(user_id, payload.title, payload.prompt)
        return json_success(prompt_id=result["prompt_id"], message="Prompt created successfully")
    except exceptions_validation.JSONError as e:
        return json_error_from_exception(e, redirect_to="/prompt")
    except exceptions_validation.UserValidate as e:
        return json_validation_error(e)


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
    return await render_template(
        templates,
        request,
        "prompts/detail.html",
        {"title": prompt.title, "prompt": prompt, "logged_in": True},
    )


async def prompt_detail_json(request: Request):
    try:
        prompt_id = int(request.path_params["prompt_id"])
        user_id = await require_user_id_json(request, message="Not authenticated")
        prompt = await prompt_repository.get_prompt(user_id, prompt_id)
    except exceptions_validation.UserValidate:
        return json_error("Prompt not found", status_code=404)
    except exceptions_validation.JSONError as e:
        return json_error_from_exception(e, redirect_to="/prompt")
    data = {
        "prompt_id": prompt.prompt_id,
        "title": prompt.title,
        "prompt": prompt.prompt,
    }
    return json_success(prompt=data)


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
    return await render_template(
        templates,
        request,
        "prompts/edit.html",
        {"title": f"Edit {prompt.title}", "prompt": prompt, "logged_in": True},
    )


async def prompt_edit_post(request: Request):
    try:
        prompt_id = int(request.path_params["prompt_id"])
        user_id = await require_user_id_json(request, message="Not authenticated")
        prompt = await prompt_repository.get_prompt(user_id, prompt_id)
        if not prompt:
            return json_error("Prompt not found", status_code=404)
        payload = await parse_json_payload(request, PromptUpsertRequest)
        await prompt_repository.update_prompt(user_id, prompt_id, payload.title, payload.prompt)
        return json_success(message="Prompt updated successfully")
    except ValueError:
        return json_error("Prompt not found", status_code=404)
    except exceptions_validation.JSONError as e:
        return json_error_from_exception(e, redirect_to="/prompt")
    except exceptions_validation.UserValidate as e:
        return json_validation_error(e)


async def prompt_delete_post(request: Request):
    try:
        prompt_id = int(request.path_params["prompt_id"])
        user_id = await require_user_id_json(request, message="Not authenticated")
        prompt = await prompt_repository.get_prompt(user_id, prompt_id)
        if not prompt:
            return json_error("Prompt not found", status_code=404)
        await prompt_repository.delete_prompt(user_id, prompt_id)
        return json_success(message="Prompt deleted successfully")
    except ValueError:
        return json_error("Prompt not found", status_code=404)
    except exceptions_validation.JSONError as e:
        return json_error_from_exception(e, redirect_to="/prompt")
    except exceptions_validation.UserValidate as e:
        return json_validation_error(e)
