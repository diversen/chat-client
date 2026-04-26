from typing import Any

from starlette.requests import Request
from starlette.responses import RedirectResponse

from chat_client.core.templates import get_templates

templates = get_templates()


async def chat_page(
    request: Request,
    *,
    get_user_id_or_redirect,
    get_model_names,
    list_prompts,
    get_context,
    default_model: str,
    build_model_capabilities,
):
    user_id_or_response = await get_user_id_or_redirect(
        request,
        notice="You must be logged in to access the chat",
    )
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response

    model_names = await get_model_names()
    prompts = await list_prompts(user_id)
    model_capabilities = build_model_capabilities()
    default_model_capabilities = model_capabilities.get(default_model, {})

    context = {
        "chat": True,
        "model_names": model_names,
        "default_model": default_model,
        "default_model_supports_images": bool(default_model_capabilities.get("supports_images")),
        "default_model_supports_attachments": bool(default_model_capabilities.get("supports_attachments")),
        "request": request,
        "title": "Chat",
        "prompts": prompts,
    }

    context = await get_context(request, context)
    return templates.TemplateResponse("home/chat.html", context)


async def get_chat_config(
    request: Request,
    *,
    frontend_config_impl,
    config: Any,
    system_message_denylist: list[str],
    vision_models: list[str],
    build_model_capabilities,
    build_model_providers,
    json_success,
):
    return await frontend_config_impl(
        request,
        config=config,
        system_message_denylist=system_message_denylist,
        vision_models=vision_models,
        build_model_capabilities=build_model_capabilities,
        build_model_providers=build_model_providers,
        json_success=json_success,
    )


async def list_chat_models(
    request: Request,
    *,
    list_models_impl,
    get_model_names,
    get_model_entries,
    json_success,
):
    return await list_models_impl(
        request,
        get_model_names=get_model_names,
        get_model_entries=get_model_entries,
        json_success=json_success,
    )
