from starlette.requests import Request
from starlette.responses import StreamingResponse, JSONResponse, RedirectResponse

from openai import OpenAI
from chat_client.core import base_context
from chat_client.core import chat_service
from chat_client.core import mcp_client
import data.config as config
import logging
import time
import json
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

MCP_MODELS = getattr(config, "MCP_MODELS", [])
MCP_SERVER_URL = getattr(config, "MCP_SERVER_URL", "")
MCP_AUTH_TOKEN = getattr(config, "MCP_AUTH_TOKEN", "")
MCP_TIMEOUT_SECONDS = float(getattr(config, "MCP_TIMEOUT_SECONDS", 20.0))
MCP_TOOLS_CACHE_SECONDS = float(getattr(config, "MCP_TOOLS_CACHE_SECONDS", 60.0))
SHOW_MCP_TOOL_CALLS = bool(getattr(config, "SHOW_MCP_TOOL_CALLS", False))
SYSTEM_MESSAGE_MODELS = getattr(config, "SYSTEM_MESSAGE_MODELS", [])
VISION_MODELS = getattr(config, "VISION_MODELS", [])
DEBUG_CHAT_PAYLOAD_LOGS = True

_mcp_tools_cache: list[dict] = []
_mcp_tools_cache_at: float = 0.0


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


def _list_mcp_tools() -> list[dict]:
    """
    Load MCP tools in OpenAI schema format with a small TTL cache.
    """
    global _mcp_tools_cache, _mcp_tools_cache_at
    now = time.monotonic()
    if _mcp_tools_cache and (now - _mcp_tools_cache_at) < MCP_TOOLS_CACHE_SECONDS:
        return _mcp_tools_cache

    tools = mcp_client.list_tools_openai_schema(
        server_url=MCP_SERVER_URL,
        auth_token=MCP_AUTH_TOKEN,
        timeout_seconds=MCP_TIMEOUT_SECONDS,
    )
    _mcp_tools_cache = tools
    _mcp_tools_cache_at = now
    return tools


def _execute_tool(tool_call):
    """
    Execute a tool call via MCP.
    """
    func_name = tool_call["function"]["name"]
    args = chat_service.parse_tool_arguments(tool_call, logger)
    logger.info(f"Executing MCP tool: {func_name}({args})")
    return mcp_client.call_tool(
        server_url=MCP_SERVER_URL,
        auth_token=MCP_AUTH_TOKEN,
        timeout_seconds=MCP_TIMEOUT_SECONDS,
        name=func_name,
        arguments=args,
    )


def _serialize_tool_content(result) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=True)
    except TypeError:
        return str(result)


def _normalize_chat_messages(messages: list) -> list:
    """
    Convert user messages with uploaded images into OpenAI content parts.
    """
    return chat_service.normalize_chat_messages(messages)


def _strip_images_from_messages(messages: list[dict]) -> list[dict]:
    """
    Remove image attachments from messages before sending to non-vision models.
    """
    stripped: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_copy = dict(message)
        message_copy["images"] = []
        stripped.append(message_copy)
    return stripped


def _summarize_messages_for_log(messages: list[dict]) -> list[dict]:
    """
    Compact message summary for temporary chat payload debugging.
    """
    summaries: list[dict] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            summaries.append({"index": index, "invalid": True})
            continue
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", ""))
        images = message.get("images", [])
        image_count = len(images) if isinstance(images, list) else 0
        summaries.append(
            {
                "index": index,
                "role": role,
                "has_images": image_count > 0,
                "image_count": image_count,
                "content_preview": content[:120],
            }
        )
    return summaries


async def _chat_response_stream(request: Request, messages, model, logged_in, dialog_id: str):
    async def _tool_executor_with_persist(tool_call):
        result_text = ""
        error_text = ""
        try:
            result = _execute_tool(tool_call)
            result_text = _serialize_tool_content(result)
            return result
        except Exception as error:
            error_text = str(error)
            raise
        finally:
            if dialog_id:
                parsed_args = chat_service.parse_tool_arguments(tool_call, logger)
                await chat_repository.create_tool_call_event(
                    user_id=logged_in,
                    dialog_id=dialog_id,
                    tool_call_id=str(tool_call.get("id", "")),
                    tool_name=str(tool_call.get("function", {}).get("name", "")),
                    arguments=parsed_args,
                    result_text=result_text,
                    error_text=error_text,
                )

    async for chunk in chat_service.chat_response_stream(
        request,
        messages,
        model,
        openai_client_cls=OpenAI,
        provider_info_resolver=_resolve_provider_info,
        tool_models=MCP_MODELS,
        tools_loader=_list_mcp_tools,
        tool_executor=_tool_executor_with_persist,
        logger=logger,
    ):
        yield chunk


async def chat_response_stream(request: Request):
    try:
        logged_in = await require_user_id_json(request, message="You must be logged in to use the chat")
        payload = await parse_json_payload(request, ChatStreamRequest)
        raw_messages = [message.model_dump() for message in payload.messages]
        stripped_images = False
        if DEBUG_CHAT_PAYLOAD_LOGS:
            logger.warning(
                "[CHAT-DEBUG] /chat input model=%s vision=%s messages=%s",
                payload.model,
                payload.model in VISION_MODELS,
                _summarize_messages_for_log(raw_messages),
            )
        if payload.model not in VISION_MODELS:
            raw_messages = _strip_images_from_messages(raw_messages)
            stripped_images = True
        if DEBUG_CHAT_PAYLOAD_LOGS:
            logger.warning(
                "[CHAT-DEBUG] /chat post-strip stripped_images=%s messages=%s",
                stripped_images,
                _summarize_messages_for_log(raw_messages),
            )
        messages = _normalize_chat_messages(raw_messages)
        if DEBUG_CHAT_PAYLOAD_LOGS:
            logger.warning(
                "[CHAT-DEBUG] /chat normalized messages=%s",
                _summarize_messages_for_log(messages),
            )
        dialog_id = str(payload.dialog_id).strip()
        if dialog_id:
            await chat_repository.get_dialog(logged_in, dialog_id)
        return StreamingResponse(
            _chat_response_stream(request, messages, payload.model, logged_in, dialog_id),
            media_type="text/event-stream",
        )
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)


async def config_(request: Request):
    """
    GET frontend configuration
    """
    config_values = {
        "default_model": getattr(config, "DEFAULT_MODEL", ""),
        "use_katex": getattr(config, "USE_KATEX", False),
        "show_mcp_tool_calls": SHOW_MCP_TOOL_CALLS,
        "system_message_models": SYSTEM_MESSAGE_MODELS,
        "vision_models": VISION_MODELS,
    }

    return JSONResponse(config_values)


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
        user_id = await require_user_id_json(request, message="You must be logged in in order to create a message")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")

        payload = await parse_json_payload(request, CreateMessageRequest)
        if payload.role == "user" and payload.images:
            selected_model = payload.model.strip()
            if not selected_model:
                raise exceptions_validation.UserValidate("Model is required when attaching images")
            if selected_model not in VISION_MODELS:
                raise exceptions_validation.UserValidate(chat_service.IMAGE_MODALITY_ERROR_MESSAGE)
        message_id = await chat_repository.create_message(
            user_id,
            dialog_id,
            payload.role,
            payload.content,
            [image.model_dump() for image in payload.images],
        )
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
        if not SHOW_MCP_TOOL_CALLS:
            messages = [message for message in messages if message.get("role") != "tool"]
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

        raw_message_id = request.path_params.get("message_id")
        if raw_message_id is None:
            raise ValueError("Missing message id")
        message_id = int(raw_message_id)
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
