"""Starlette routes for Prompt CRUD."""

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse
from chat_client.core.templates import get_templates
from chat_client.core.base_context import get_context
from chat_client.core import user_session

# from chat_client.core.exceptions import UserValidate
from chat_client.core import exceptions_validation
from chat_client.repositories import prompt_repository

templates = get_templates()


async def prompt_list(request: Request):
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        return RedirectResponse("/user/login")
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
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        return JSONResponse({"error": True, "message": "Not authenticated"}, status_code=401)
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


async def prompt_create_form(request: Request):
    if not await user_session.is_logged_in(request):
        return RedirectResponse("/user/login")
    context = {
        "request": request,
        "title": "Create Prompt",
        "logged_in": True,
    }
    context = await get_context(request, context)
    return templates.TemplateResponse("prompts/create.html", context)


async def prompt_create(request: Request):
    try:
        user_id = await user_session.is_logged_in(request)
        if not user_id:
            return JSONResponse({"error": True, "message": "Not authenticated"}, status_code=401)

        result = await prompt_repository.create_prompt(user_id, request)
        return JSONResponse({"error": False, "prompt_id": result["prompt_id"]})
    except exceptions_validation.UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})


async def prompt_detail(request: Request):
    prompt_id = int(request.path_params["prompt_id"])
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        return RedirectResponse("/user/login")
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
    prompt_id = int(request.path_params["prompt_id"])
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        return JSONResponse({"error": True, "message": "Not authenticated"}, status_code=401)
    try:
        prompt = await prompt_repository.get_prompt(user_id, prompt_id)
    except exceptions_validation.UserValidate:
        return JSONResponse({"error": True, "message": "Prompt not found"}, status_code=404)
    data = {
        "prompt_id": prompt.prompt_id,
        "title": prompt.title,
        "prompt": prompt.prompt,
    }
    return JSONResponse({"error": False, "prompt": data})


async def prompt_edit_form(request: Request):
    prompt_id = int(request.path_params["prompt_id"])
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        return RedirectResponse("/user/login")
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


async def prompt_edit(request: Request):

    prompt_id = int(request.path_params["prompt_id"])
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        return RedirectResponse("/user/login")

    prompt = await prompt_repository.get_prompt(user_id, prompt_id)
    if not prompt:
        return JSONResponse({"error": True, "message": "Prompt not found"}, status_code=404)

    try:
        await prompt_repository.update_prompt(request, prompt_id)
        return JSONResponse({"error": False})
    except exceptions_validation.UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})


async def prompt_delete(request: Request):
    prompt_id = int(request.path_params["prompt_id"])
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        return RedirectResponse("/user/login")
    prompt = await prompt_repository.get_prompt(user_id, prompt_id)

    if not prompt:
        return JSONResponse({"error": True, "message": "Prompt not found"}, status_code=404)
    try:
        await prompt_repository.delete_prompt(request, prompt_id)
        return JSONResponse({"error": False})
    except exceptions_validation.UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})


routes_prompt = [
    Route("/prompt", prompt_list, methods=["GET"]),
    Route("/prompt/json", prompt_list_json, methods=["GET"]),
    Route("/prompt/create", prompt_create_form, methods=["GET"]),
    Route("/prompt/create", prompt_create, methods=["POST"]),
    Route("/prompt/{prompt_id:int}", prompt_detail, methods=["GET"]),
    Route("/prompt/{prompt_id:int}/edit", prompt_edit_form, methods=["GET"]),
    Route("/prompt/{prompt_id:int}/edit", prompt_edit, methods=["POST"]),
    Route("/prompt/{prompt_id:int}/delete", prompt_delete, methods=["POST"]),
    Route("/prompt/{prompt_id:int}/json", prompt_detail_json, methods=["GET"]),
]
