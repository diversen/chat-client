from starlette.requests import Request
from starlette.responses import StreamingResponse, JSONResponse, RedirectResponse

from openai import OpenAI
from chat_client.core import base_context
from chat_client.core import chat_service
import data.config as config
import logging
from chat_client.core.templates import get_templates
from chat_client.repositories import chat_repository, user_repository, prompt_repository
from chat_client.core import exceptions_validation
from chat_client.core.http import (
    parse_json_payload,
    require_user_id_json,
    get_user_id_or_redirect,
    json_error,
    json_success,
)
from chat_client.schemas.chat import (
    ChatStreamRequest,
    CreateDialogRequest,
    CreateMessageRequest,
    UpdateMessageRequest,
)

# Logger
logger: logging.Logger = logging.getLogger(__name__)
templates = get_templates()

MODELS = getattr(config, "MODELS", {})
PROVIDERS = getattr(config, "PROVIDERS", {})

TOOL_REGISTRY = getattr(config, "TOOL_REGISTRY", {})
TOOLS = getattr(config, "TOOLS", [])
TOOL_MODELS = getattr(config, "TOOL_MODELS", [])


def _resolve_provider_info(model: str) -> dict:
    return chat_service.resolve_provider_info(model, MODELS, PROVIDERS)


async def chat_page(request: Request):
    """
    The GET chat page
    """
    user_id_or_response = await get_user_id_or_redirect(
        request,
        notice="You must be logged in to access the chat",
    )
    if isinstance(user_id_or_response, RedirectResponse):
        return user_id_or_response
    user_id = user_id_or_response

    model_names = await _get_model_names()
    prompts = await prompt_repository.list_prompts(user_id)

    context = {
        "chat": True,
        "model_names": model_names,
        "default_model": getattr(config, "DEFAULT_MODEL", ""),
        "request": request,
        "title": "Chat",
        "prompts": prompts,
    }

    context = await base_context.get_context(request, context)
    return templates.TemplateResponse("home/chat.html", context)


def _execute_tool(tool_call):
    """
    Execute a tool call
    """
    return chat_service.execute_tool(tool_call, TOOL_REGISTRY, logger)


def _normalize_chat_messages(messages: list) -> list:
    """
    Convert user messages with uploaded images into OpenAI content parts.
    """
    return chat_service.normalize_chat_messages(messages)


async def _chat_response_stream(request: Request, messages, model, logged_in):
    async for chunk in chat_service.chat_response_stream(
        request,
        messages,
        model,
        logged_in,
        get_profile=user_repository.get_profile,
        openai_client_cls=OpenAI,
        provider_info_resolver=_resolve_provider_info,
        tool_models=TOOL_MODELS,
        tools=TOOLS,
        tool_executor=_execute_tool,
        logger=logger,
    ):
        yield chunk


async def chat_response_stream(request: Request):
    try:
        logged_in = await require_user_id_json(request, message="You must be logged in to use the chat")
        payload = await parse_json_payload(request, ChatStreamRequest)
        messages = _normalize_chat_messages([message.model_dump() for message in payload.messages])
        return StreamingResponse(
            _chat_response_stream(request, messages, payload.model, logged_in),
            media_type="text/event-stream",
        )
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)


async def config_(request: Request):
    """
    GET frontend configuration
    """
    config_ = {
        "default_model": getattr(config, "DEFAULT_MODEL", ""),
        "tools_callback": getattr(config, "TOOLS_CALLBACK", {}),
        "use_katex": getattr(config, "USE_KATEX", False),
    }

    return JSONResponse(config_)


async def json_tools(request: Request):
    """
    POST endpoint for calling tools

    A tool can call this endpoint using JSON data.
    The server will then call a function
    The JSON data is in the form of which specify the tool to call

    {
        "module": "ollama_serv.tools.python_exec",
        "def": "execute",
    }

    """

    try:
        await require_user_id_json(request, message="You must be logged in to use tools")
        data = await request.json()
        tool = request.path_params["tool"]

        tools_callback = getattr(config, "TOOLS_CALLBACK", {})
        tool_def = tools_callback.get(tool, {})
        if not tool_def:
            return JSONResponse({"tool": tool, "text": "Tool not found"}, status_code=404)

        # import module and call function
        module = __import__(tool_def["module"], fromlist=[tool_def["def"]])
        function = getattr(module, tool_def["def"])
        ret_data = function(data)
        logger.debug(f"Tool result: {ret_data}")
        return JSONResponse({"tool": tool, "text": ret_data})
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except Exception:
        tool_name = request.path_params.get("tool", "unknown")
        logger.exception(f"Error calling tool {tool_name}")
        return json_error("Tool execution failed", status_code=500, tool=tool_name)


async def _get_model_names():
    return list(MODELS.keys())


async def list_models(request: Request):
    """
    GET available models
    """

    model_names = await _get_model_names()
    return JSONResponse({"model_names": model_names})


async def create_dialog(request: Request):
    """
    Save dialog to database
    """
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to save a dialog")
        payload = await parse_json_payload(request, CreateDialogRequest)
        dialog_id = await chat_repository.create_dialog(user_id, payload.title)
        return json_success(dialog_id=dialog_id, message="Dialog saved")
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error saving dialog")
        return json_error("Error saving dialog", status_code=500)


async def create_message(request: Request):
    """
    Save message to database
    """
    try:
        user_id = await require_user_id_json(request, message="You must be logged in create a message")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")

        payload = await parse_json_payload(request, CreateMessageRequest)
        message_id = await chat_repository.create_message(user_id, dialog_id, payload.role, payload.content)
        return JSONResponse({"message_id": message_id})
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error saving message")
        return json_error("Error saving message", status_code=500)


async def get_dialog(request: Request):
    """
    Get dialog from database
    """
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to get a dialog")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")
        dialog = await chat_repository.get_dialog(user_id, dialog_id)
        return JSONResponse(dialog)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error getting dialog")
        return json_error("Error getting dialog", status_code=500)


async def get_messages(request: Request):
    """
    Get messages from database
    """
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to get a dialog")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")
        messages = await chat_repository.get_messages(user_id, dialog_id)
        return JSONResponse(messages)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error getting messages")
        return json_error("Error getting messages", status_code=500)


async def delete_dialog(request: Request):
    """
    Delete dialog from database
    """
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to delete a dialog")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")
        await chat_repository.delete_dialog(user_id, dialog_id)
        return json_success()
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error deleting dialog")
        return json_error("Error deleting dialog", status_code=500)


async def update_message(request: Request):
    """
    Update message content and deactivate newer messages in the same dialog
    """
    try:
        user_id = await require_user_id_json(
            request,
            message="You must be logged in to update a message",
        )

        message_id = int(request.path_params.get("message_id"))
        payload = await parse_json_payload(request, UpdateMessageRequest)
        result = await chat_repository.update_message(user_id, message_id, payload.content)
        return json_success(**result)
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except (TypeError, ValueError):
        return json_error("Invalid message id", status_code=400)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error updating message")
        return json_error("Error updating message", status_code=500)

