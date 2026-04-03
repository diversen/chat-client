import asyncio
from html import escape
import time
import json
import logging
import uuid
from pathlib import Path
from typing import Any

import data.config as config
from openai import OpenAI
from starlette.requests import Request
from starlette.responses import StreamingResponse, JSONResponse, RedirectResponse, FileResponse, PlainTextResponse

from chat_client.core import base_context
from chat_client.core import attachments as attachment_service
from chat_client.core import chat_service
from chat_client.core import config_utils
from chat_client.core import mcp_client
from chat_client.core import model_capabilities
from chat_client.core import tool_executor
from chat_client.core.templates import get_templates
from chat_client.repositories import attachment_repository, chat_repository, prompt_repository
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
    CreateAssistantTurnEventsRequest,
    CreateDialogRequest,
    CreateMessageRequest,
    GenerateDialogTitleRequest,
    UpdateMessageRequest,
)
# Logger
logger: logging.Logger = logging.getLogger(__name__)
templates = get_templates()

CONFIGURED_MODELS = getattr(config, "MODELS", {})
CONFIGURED_PROVIDERS = getattr(config, "PROVIDERS", {})

CONFIGURED_MCP_SERVER_URL = getattr(config, "MCP_SERVER_URL", "")
CONFIGURED_MCP_AUTH_TOKEN = getattr(config, "MCP_AUTH_TOKEN", "")
RESOLVED_MCP_TIMEOUT_SECONDS = float(getattr(config, "MCP_TIMEOUT_SECONDS", 20.0))
RESOLVED_MCP_TOOLS_CACHE_SECONDS = float(getattr(config, "MCP_TOOLS_CACHE_SECONDS", 60.0))
CONFIGURED_SYSTEM_MESSAGE_DENYLIST = getattr(config, "SYSTEM_MESSAGE_DENYLIST", [])
CONFIGURED_VISION_MODELS = getattr(config, "VISION_MODELS", [])
CONFIGURED_TOOL_REGISTRY = getattr(config, "TOOL_REGISTRY", {})
CONFIGURED_LOCAL_TOOL_DEFINITIONS = getattr(config, "LOCAL_TOOL_DEFINITIONS", [])
CONFIGURED_TOOL_MODELS = getattr(config, "TOOL_MODELS", [])
RESOLVED_CHAT_MAX_LOOP_ROUNDS = getattr(config, "CHAT_MAX_LOOP_ROUNDS", chat_service.DEFAULT_CHAT_MAX_LOOP_ROUNDS)

# Backward-compatible aliases for existing patch points in tests and local imports.
MODELS = config_utils.resolve_models(CONFIGURED_MODELS, CONFIGURED_PROVIDERS)
PROVIDERS = CONFIGURED_PROVIDERS
MCP_SERVER_URL = CONFIGURED_MCP_SERVER_URL
MCP_AUTH_TOKEN = CONFIGURED_MCP_AUTH_TOKEN
MCP_TIMEOUT_SECONDS = RESOLVED_MCP_TIMEOUT_SECONDS
MCP_TOOLS_CACHE_SECONDS = RESOLVED_MCP_TOOLS_CACHE_SECONDS
SYSTEM_MESSAGE_DENYLIST = CONFIGURED_SYSTEM_MESSAGE_DENYLIST
VISION_MODELS = CONFIGURED_VISION_MODELS
TOOL_REGISTRY = CONFIGURED_TOOL_REGISTRY
LOCAL_TOOL_DEFINITIONS = CONFIGURED_LOCAL_TOOL_DEFINITIONS
TOOL_MODELS = CONFIGURED_TOOL_MODELS
CHAT_MAX_LOOP_ROUNDS = RESOLVED_CHAT_MAX_LOOP_ROUNDS

_mcp_tools_cache: list[dict] = []
_mcp_tools_cache_at: float = 0.0


def _resolve_provider_info(model: str) -> dict:
    return chat_service.resolve_provider_info(model, MODELS, PROVIDERS)


def _model_capabilities_cache_token() -> dict[str, Any]:
    return {
        "providers": PROVIDERS,
        "models": MODELS,
        "vision_models": VISION_MODELS,
        "tool_models": TOOL_MODELS,
        "system_message_denylist": SYSTEM_MESSAGE_DENYLIST,
    }


def _has_local_tool_registry() -> bool:
    return isinstance(TOOL_REGISTRY, dict) and bool(TOOL_REGISTRY)


def _has_mcp_config() -> bool:
    return bool(MCP_SERVER_URL.strip())


def _normalize_local_tool_definition(tool_definition: dict[str, Any]) -> dict[str, Any] | None:
    return tool_executor.normalize_local_tool_definition(tool_definition, TOOL_REGISTRY)


def _get_local_tool_definition(name: str) -> dict[str, Any] | None:
    return tool_executor.get_local_tool_definition(
        name,
        tool_registry=TOOL_REGISTRY,
        local_tool_definitions=LOCAL_TOOL_DEFINITIONS,
    )


def _list_local_tools() -> list[dict[str, Any]]:
    return tool_executor.list_local_tools(
        tool_registry=TOOL_REGISTRY,
        local_tool_definitions=LOCAL_TOOL_DEFINITIONS,
    )


def _resolve_tool_models() -> list[str]:
    return model_capabilities.resolve_tool_models(
        models=MODELS,
        vision_models=VISION_MODELS,
        tool_models=TOOL_MODELS,
        system_message_denylist=SYSTEM_MESSAGE_DENYLIST,
        provider_info_resolver=_resolve_provider_info,
        cache_token=_model_capabilities_cache_token(),
    )


def _build_model_capabilities() -> dict[str, dict[str, bool]]:
    return model_capabilities.build_model_capabilities(
        models=MODELS,
        vision_models=VISION_MODELS,
        tool_models=TOOL_MODELS,
        system_message_denylist=SYSTEM_MESSAGE_DENYLIST,
        provider_info_resolver=_resolve_provider_info,
        cache_token=_model_capabilities_cache_token(),
    )


def _supports_model_images(model_name: str) -> bool:
    return model_capabilities.supports_model_images(
        model_name=model_name,
        models=MODELS,
        vision_models=VISION_MODELS,
        tool_models=TOOL_MODELS,
        system_message_denylist=SYSTEM_MESSAGE_DENYLIST,
        provider_info_resolver=_resolve_provider_info,
        cache_token=_model_capabilities_cache_token(),
    )


def _supports_model_attachments(model_name: str) -> bool:
    return model_capabilities.supports_model_attachments(
        model_name=model_name,
        models=MODELS,
        vision_models=VISION_MODELS,
        tool_models=TOOL_MODELS,
        system_message_denylist=SYSTEM_MESSAGE_DENYLIST,
        provider_info_resolver=_resolve_provider_info,
        cache_token=_model_capabilities_cache_token(),
    )


def log_model_capabilities_summary(logger_: logging.Logger | None = None) -> dict[str, dict[str, bool]]:
    return model_capabilities.warm_and_log_model_capabilities(
        logger=logger_ or logger,
        models=MODELS,
        vision_models=VISION_MODELS,
        tool_models=TOOL_MODELS,
        system_message_denylist=SYSTEM_MESSAGE_DENYLIST,
        provider_info_resolver=_resolve_provider_info,
        cache_token=_model_capabilities_cache_token(),
    )


def _attachment_preview_is_image(content_type: str, suffix: str) -> bool:
    normalized = str(content_type or "").strip().lower()
    return normalized.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _attachment_preview_is_text(content_type: str, suffix: str) -> bool:
    normalized = str(content_type or "").strip().lower()
    if normalized in {
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/x-python-code",
        "text/x-python",
        "application/xml",
        "text/xml",
        "text/html",
    }:
        return True
    return suffix in {".txt", ".md", ".markdown", ".csv", ".json", ".py", ".yaml", ".yml", ".log", ".xml", ".html", ".htm"}


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


def _list_tools() -> list[dict]:
    tools: list[dict] = []
    if _has_local_tool_registry():
        tools.extend(_list_local_tools())
    if _has_mcp_config():
        tools.extend(_list_mcp_tools())
    return tools


def _find_tool_definition(name: str) -> dict[str, Any] | None:
    return tool_executor.find_tool_definition(name, _list_tools())


def _get_local_tool_execution_options(name: str) -> dict[str, Any]:
    return tool_executor.get_local_tool_execution_options(
        name,
        tool_registry=TOOL_REGISTRY,
        local_tool_definitions=LOCAL_TOOL_DEFINITIONS,
    )


def _local_tool_accepts_attachment_workspace(name: str) -> bool:
    return tool_executor.local_tool_accepts_attachment_workspace(name, TOOL_REGISTRY)


def _tool_uses_workspace_mount(name: str) -> bool:
    return tool_executor.tool_uses_workspace_mount(
        name,
        tool_registry=TOOL_REGISTRY,
        local_tool_definitions=LOCAL_TOOL_DEFINITIONS,
    )


def _execute_local_tool_with_runtime_context(
    tool_call: dict[str, Any],
    *,
    log_context: dict[str, Any] | None = None,
    available_attachments: list[dict[str, Any]] | None = None,
):
    return tool_executor.execute_local_tool_with_runtime_context(
        tool_call,
        logger=logger,
        tools=_list_tools(),
        tool_registry=TOOL_REGISTRY,
        local_tool_definitions=LOCAL_TOOL_DEFINITIONS,
        has_local_tool_registry=_has_local_tool_registry(),
        has_mcp_config=_has_mcp_config(),
        mcp_server_url=MCP_SERVER_URL,
        mcp_auth_token=MCP_AUTH_TOKEN,
        mcp_timeout_seconds=MCP_TIMEOUT_SECONDS,
        log_context=log_context,
        available_attachments=available_attachments,
    )


def _build_chat_log_context(
    *,
    trace_id: str = "",
    user_id: Any = None,
    dialog_id: str = "",
    model: str = "",
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "user_id": user_id,
        "dialog_id": dialog_id,
        "model": model,
    }


def _log_chat_event(level: int, event: str, **fields: Any) -> None:
    payload = {key: value for key, value in fields.items() if value is not None}
    logger.log(level, "%s: %s", event, payload)


def _new_trace_id() -> str:
    return uuid.uuid4().hex[:12]


def _execute_tool(
    tool_call,
    *,
    log_context: dict[str, Any] | None = None,
    argument_overrides: dict[str, Any] | None = None,
):
    return tool_executor.execute_tool(
        tool_call,
        logger=logger,
        tools=_list_tools(),
        tool_registry=TOOL_REGISTRY,
        local_tool_definitions=LOCAL_TOOL_DEFINITIONS,
        has_local_tool_registry=_has_local_tool_registry(),
        has_mcp_config=_has_mcp_config(),
        mcp_server_url=MCP_SERVER_URL,
        mcp_auth_token=MCP_AUTH_TOKEN,
        mcp_timeout_seconds=MCP_TIMEOUT_SECONDS,
        log_context=log_context,
        argument_overrides=argument_overrides,
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


def _build_model_messages_from_dialog_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Build provider-compatible messages from persisted dialog history.
    Includes tool messages so prior tool outputs stay in context.
    """
    normalized: list[dict[str, Any]] = []
    i = 0
    while i < len(messages):
        message = messages[i]
        if not isinstance(message, dict):
            i += 1
            continue
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", ""))

        if role == "assistant_turn":
            events = message.get("events", [])
            if not isinstance(events, list):
                i += 1
                continue
            pending_tool_calls: list[dict[str, Any]] = []
            pending_tool_messages: list[dict[str, Any]] = []
            for raw_event in events:
                if not isinstance(raw_event, dict):
                    continue
                event_type = str(raw_event.get("event_type", "")).strip()
                if event_type == "assistant_segment":
                    if pending_tool_calls:
                        normalized.append(
                            {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": pending_tool_calls,
                            }
                        )
                        normalized.extend(pending_tool_messages)
                        pending_tool_calls = []
                        pending_tool_messages = []
                    content_text = str(raw_event.get("content_text", ""))
                    if content_text.strip():
                        normalized.append({"role": "assistant", "content": content_text})
                    continue
                if event_type == "tool_call":
                    tool_call_id = str(raw_event.get("tool_call_id", "")).strip()
                    tool_name = str(raw_event.get("tool_name", "")).strip() or "unknown_tool"
                    raw_arguments = raw_event.get("arguments_json", "{}")
                    arguments_json = "{}"
                    if isinstance(raw_arguments, str):
                        try:
                            parsed_arguments = json.loads(raw_arguments)
                            arguments_json = json.dumps(parsed_arguments, ensure_ascii=True, separators=(",", ":"))
                        except json.JSONDecodeError:
                            arguments_json = "{}"
                    pending_tool_calls.append(
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": arguments_json,
                            },
                        }
                    )
                    pending_tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": str(raw_event.get("result_text", "") or raw_event.get("error_text", "")),
                        }
                    )
            if pending_tool_calls:
                normalized.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": pending_tool_calls,
                    }
                )
                normalized.extend(pending_tool_messages)
            i += 1
            continue

        if role in {"user", "assistant", "system"}:
            item: dict[str, Any] = {"role": role, "content": content}
            if role == "user":
                images = message.get("images", [])
                item["images"] = images if isinstance(images, list) else []
                attachments = message.get("attachments", [])
                item["attachments"] = attachments if isinstance(attachments, list) else []
            normalized.append(item)
            i += 1
            continue

        if role == "tool":
            consecutive_tools: list[dict[str, Any]] = []
            while i < len(messages):
                candidate = messages[i]
                if not isinstance(candidate, dict):
                    break
                if str(candidate.get("role", "")).strip() != "tool":
                    break
                tool_call_id = str(candidate.get("tool_call_id", "")).strip()
                if tool_call_id:
                    consecutive_tools.append(candidate)
                i += 1

            if not consecutive_tools:
                continue

            tool_calls: list[dict[str, Any]] = []
            for tool_message in consecutive_tools:
                tool_call_id = str(tool_message.get("tool_call_id", "")).strip()
                tool_name = str(tool_message.get("tool_name", "")).strip() or "unknown_tool"
                raw_arguments = tool_message.get("arguments_json", "{}")
                arguments_json = "{}"
                if isinstance(raw_arguments, str):
                    try:
                        parsed_arguments = json.loads(raw_arguments)
                        arguments_json = json.dumps(parsed_arguments, ensure_ascii=True, separators=(",", ":"))
                    except json.JSONDecodeError:
                        arguments_json = "{}"

                tool_calls.append(
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": arguments_json,
                        },
                    }
                )

            normalized.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": tool_calls,
                }
            )
            for tool_message in consecutive_tools:
                tool_call_id = str(tool_message.get("tool_call_id", "")).strip()
                normalized.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": str(tool_message.get("content", "")),
                    }
                )
            continue
        i += 1
    return normalized


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


TITLE_GENERATION_MAX_TOKENS = 24
TITLE_FALLBACK_MAX_LENGTH = 80
PENDING_DIALOG_TITLES = {"New chat"}


def _normalize_generated_dialog_title(value: str, fallback: str) -> str:
    normalized = str(value or "").strip()
    normalized = normalized.strip(" \t\r\n\"'`")
    normalized = " ".join(normalized.split())
    if not normalized:
        normalized = str(fallback or "").strip()
    if len(normalized) > TITLE_FALLBACK_MAX_LENGTH:
        normalized = normalized[:TITLE_FALLBACK_MAX_LENGTH].rstrip(" ,.;:-")
    return normalized or "New chat"


def _is_pending_dialog_title(title: str) -> bool:
    normalized_title = str(title or "").strip()
    return normalized_title in PENDING_DIALOG_TITLES or normalized_title.startswith("Attachment message (")


def _extract_dialog_title_context(messages: list[dict[str, Any]]) -> tuple[str, str]:
    first_user_message = ""
    first_assistant_message = ""

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = str(message.get("role", "")).strip()
        if not first_user_message and role == "user":
            first_user_message = str(message.get("content", "")).strip()
            continue

        if first_assistant_message:
            continue

        if role == "assistant":
            content = str(message.get("content", "")).strip()
            if content:
                first_assistant_message = content
            continue

        if role != "assistant_turn":
            continue

        events = message.get("events", [])
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            if str(event.get("event_type", "")).strip() != "assistant_segment":
                continue
            content = str(event.get("content_text", "")).strip()
            if content:
                first_assistant_message = content
                break

    return first_user_message, first_assistant_message


def _build_dialog_title_prompt(user_content: str, assistant_content: str) -> list[dict[str, str]]:
    normalized_user_content = str(user_content or "").strip()
    normalized_assistant_content = str(assistant_content or "").strip()
    return [
        {
            "role": "system",
            "content": (
                "Generate a short title for a chat based on the opening exchange. "
                "Return only the title. Use 3 to 7 words when possible. "
                "Do not use quotes. Do not add labels or explanations."
            ),
        },
        {
            "role": "user",
            "content": (
                f"First user message:\n{normalized_user_content}\n\n"
                f"First assistant response:\n{normalized_assistant_content}"
            ),
        },
    ]


def _generate_dialog_title(user_content: str, assistant_content: str, model: str) -> str:
    normalized_user_content = str(user_content or "").strip()
    normalized_assistant_content = str(assistant_content or "").strip()
    selected_model = str(model or "").strip()
    if not normalized_user_content:
        raise exceptions_validation.UserValidate("User content is required to generate a dialog title")
    if not normalized_assistant_content:
        raise exceptions_validation.UserValidate("Assistant content is required to generate a dialog title")
    if not selected_model:
        raise exceptions_validation.UserValidate("Model is required to generate a dialog title")

    provider_info = _resolve_provider_info(selected_model)
    client = OpenAI(
        api_key=provider_info.get("api_key"),
        base_url=provider_info.get("base_url"),
    )
    response = client.chat.completions.create(
        model=selected_model,
        messages=_build_dialog_title_prompt(normalized_user_content, normalized_assistant_content),
        stream=False,
        max_tokens=TITLE_GENERATION_MAX_TOKENS,
    )
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return _normalize_generated_dialog_title("", normalized_user_content)
    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    raw_content = getattr(message, "content", "") if message is not None else ""
    return _normalize_generated_dialog_title(str(raw_content or ""), normalized_user_content)


async def _chat_response_stream(
    request: Request,
    messages,
    model,
    logged_in,
    dialog_id: str,
    trace_id: str,
    available_attachments: list[dict[str, Any]] | None = None,
):
    log_context = _build_chat_log_context(trace_id=trace_id, user_id=logged_in, dialog_id=dialog_id, model=model)
    tool_attachments = list(available_attachments or [])

    async def _tool_executor_with_persist(tool_call):
        result_text = ""
        error_text = ""
        started_at = time.perf_counter()
        try:
            func_name = str(tool_call.get("function", {}).get("name", "")).strip()
            result = await asyncio.to_thread(
                _execute_local_tool_with_runtime_context,
                tool_call,
                log_context=log_context,
                available_attachments=tool_attachments,
            )
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
                _log_chat_event(
                    logging.INFO if not error_text else logging.WARNING,
                    "chat.tool.persisted" if not error_text else "chat.tool.persist_error",
                    duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                    **chat_service.summarize_tool_result_for_log(tool_call, result_text, error_text),
                    **log_context,
                )

    async for chunk in chat_service.chat_response_stream(
        request,
        messages,
        model,
        openai_client_cls=OpenAI,
        provider_info_resolver=_resolve_provider_info,
        tool_models=_resolve_tool_models(),
        tools_loader=_list_tools,
        tool_executor=_tool_executor_with_persist,
        max_chat_loop_rounds=CHAT_MAX_LOOP_ROUNDS,
        logger=logger,
        trace_id=trace_id,
        user_id=logged_in,
        dialog_id=dialog_id,
    ):
        yield chunk


async def chat_response_stream(request: Request):
    try:
        logged_in = await require_user_id_json(request, message="You must be logged in to use the chat")
        trace_id = _new_trace_id()
        payload = await parse_json_payload(request, ChatStreamRequest)
        payload_messages = [message.model_dump() for message in payload.messages]
        raw_messages = payload_messages
        dialog_id = str(payload.dialog_id).strip()
        available_attachments: list[dict[str, Any]] = []
        log_context = _build_chat_log_context(trace_id=trace_id, user_id=logged_in, dialog_id=dialog_id, model=payload.model)
        _log_chat_event(
            logging.INFO,
            "chat.request.start",
            request_path=str(request.url.path),
            **chat_service.summarize_messages_for_log(payload_messages),
            **log_context,
        )
        if dialog_id:
            await chat_repository.get_dialog(logged_in, dialog_id)
            persisted_messages = await chat_repository.get_messages(logged_in, dialog_id)
            raw_messages = _build_model_messages_from_dialog_history(persisted_messages)
            _log_chat_event(
                logging.INFO,
                "chat.request.loaded_dialog",
                persisted_message_count=len(persisted_messages),
                **chat_service.summarize_messages_for_log(raw_messages),
                **log_context,
            )
        for candidate in reversed(raw_messages):
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("role", "")).strip() != "user":
                continue
            attachments = candidate.get("attachments", [])
            if not isinstance(attachments, list) or not attachments:
                break
            available_attachments = await attachment_repository.get_attachments(
                logged_in,
                [
                    int(attachment.get("attachment_id"))
                    for attachment in attachments
                    if isinstance(attachment, dict) and attachment.get("attachment_id") is not None
                ],
            )
            break
        if payload.model not in VISION_MODELS:
            raw_messages = _strip_images_from_messages(raw_messages)
            _log_chat_event(
                logging.DEBUG,
                "chat.request.images_stripped",
                **chat_service.summarize_messages_for_log(raw_messages),
                **log_context,
            )
        messages = _normalize_chat_messages(raw_messages)
        _log_chat_event(
            logging.INFO,
            "chat.request.normalized",
            **chat_service.summarize_messages_for_log(messages),
            **chat_service.summarize_last_user_message_for_log(messages),
            **log_context,
        )
        return StreamingResponse(
            _chat_response_stream(
                request,
                messages,
                payload.model,
                logged_in,
                dialog_id,
                trace_id,
                available_attachments=available_attachments,
            ),
            media_type="text/event-stream",
        )
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)


async def upload_attachment(request: Request):
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to upload files")
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "filename"):
            raise exceptions_validation.UserValidate("A file upload is required.")

        filename = str(getattr(upload, "filename", "") or "").strip()
        content_type = str(getattr(upload, "content_type", "") or "").strip().lower()
        file_bytes = await upload.read()
        size_bytes = len(file_bytes)
        safe_name, normalized_content_type = attachment_service.validate_attachment_metadata(
            filename,
            content_type,
            size_bytes,
        )
        attachment_id = await attachment_repository.create_attachment(
            user_id=user_id,
            name=safe_name,
            content_type=normalized_content_type or content_type,
            size_bytes=size_bytes,
            storage_path="",
        )
        if not attachment_id:
            raise RuntimeError("Failed to create attachment id")

        storage_path = attachment_service.build_attachment_storage_path(attachment_id, safe_name)
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(file_bytes)
        await attachment_repository.update_attachment_storage_path(user_id, int(attachment_id), str(storage_path))
        attachment = await attachment_repository.get_attachment(user_id, int(attachment_id))
        return JSONResponse(attachment_service.serialize_attachment_response(attachment))
    except attachment_service.AttachmentValidationError as e:
        return json_error(str(e), status_code=400)
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error uploading attachment")
        return json_error("Error uploading attachment", status_code=500)


async def preview_attachment(request: Request):
    try:
        user_id_or_response = await get_user_id_or_redirect(
            request,
            notice="You must be logged in to preview attachments",
        )
        if not isinstance(user_id_or_response, int):
            return user_id_or_response

        attachment_id = int(request.path_params.get("attachment_id", 0))
        attachment = await attachment_repository.get_attachment(user_id_or_response, attachment_id)
        storage_path = Path(str(attachment.get("storage_path", "") or "")).expanduser()
        if not storage_path.is_file():
            return json_error("Attachment file was not found on disk.", status_code=404)

        filename = str(attachment.get("name", "") or storage_path.name)
        content_type = str(attachment.get("content_type", "") or "").strip().lower()
        suffix = storage_path.suffix.lower()

        if _attachment_preview_is_image(content_type, suffix):
            response = FileResponse(str(storage_path), media_type=content_type or None, filename=filename)
            response.headers["Content-Disposition"] = f'inline; filename="{escape(filename, quote=True)}"'
            return response

        if _attachment_preview_is_text(content_type, suffix):
            text_content = storage_path.read_text(encoding="utf-8", errors="replace")
            return PlainTextResponse(text_content, media_type="text/plain")

        response = FileResponse(
            str(storage_path),
            media_type=content_type or "application/octet-stream",
            filename=filename,
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{escape(filename, quote=True)}"'
        return response
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=404)
    except ValueError:
        return json_error("Attachment id is invalid.", status_code=400)
    except Exception:
        logger.exception("Error previewing attachment")
        return json_error("Error previewing attachment", status_code=500)


async def config_(request: Request):
    """
    GET frontend configuration
    """
    config_values = {
        "default_model": getattr(config, "DEFAULT_MODEL", ""),
        "use_katex": getattr(config, "USE_KATEX", False),
        "system_message_denylist": SYSTEM_MESSAGE_DENYLIST,
        "vision_models": VISION_MODELS,
        "model_capabilities": _build_model_capabilities(),
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
            if not _supports_model_images(selected_model):
                raise exceptions_validation.UserValidate(chat_service.IMAGE_MODALITY_ERROR_MESSAGE)
        if payload.role == "user" and payload.attachments:
            selected_model = payload.model.strip()
            if not selected_model:
                raise exceptions_validation.UserValidate("Model is required when attaching files")
            if not _supports_model_attachments(selected_model):
                raise exceptions_validation.UserValidate("The selected model does not support file attachments.")
        if payload.attachments:
            await attachment_repository.get_attachments(
                user_id,
                [attachment.attachment_id for attachment in payload.attachments],
            )
        message_id = await chat_repository.create_message(
            user_id,
            dialog_id,
            payload.role,
            payload.content,
            [image.model_dump() for image in payload.images],
            [attachment.model_dump() for attachment in payload.attachments],
        )
        return JSONResponse({"message_id": message_id})
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error saving message")
        return json_error("Error saving message", status_code=500)


async def generate_dialog_title(request: Request):
    """
    Generate and persist a dialog title using the selected model.
    """
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to update a dialog title")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")

        payload = await parse_json_payload(request, GenerateDialogTitleRequest)
        dialog = await chat_repository.get_dialog(user_id, dialog_id)
        existing_title = str(dialog.get("title", "")).strip()
        if not _is_pending_dialog_title(existing_title):
            return json_success(dialog_id=dialog_id, title=existing_title, generated=False)

        messages = await chat_repository.get_messages(user_id, dialog_id)
        first_user_message, first_assistant_message = _extract_dialog_title_context(messages)
        if not first_user_message or not first_assistant_message:
            return json_success(dialog_id=dialog_id, title=existing_title, generated=False)

        generated_title = await asyncio.to_thread(
            _generate_dialog_title,
            first_user_message,
            first_assistant_message,
            payload.model,
        )
        _log_chat_event(
            logging.INFO,
            "chat.dialog_title.generated",
            user_id=user_id,
            dialog_id=dialog_id,
            model=payload.model,
            generated_title=generated_title,
        )
        result = await chat_repository.update_dialog_title(user_id, dialog_id, generated_title)
        return json_success(**result, generated=True)
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error generating dialog title")
        return json_error("Error generating dialog title", status_code=500)


async def create_assistant_turn_events(request: Request):
    """
    Save one completed assistant turn as ordered events.
    """
    try:
        user_id = await require_user_id_json(request, message="You must be logged in in order to create assistant turn events")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")
        await chat_repository.get_dialog(user_id, dialog_id)
        payload = await parse_json_payload(request, CreateAssistantTurnEventsRequest)
        await chat_repository.create_assistant_turn_events(
            user_id=user_id,
            dialog_id=dialog_id,
            turn_id=payload.turn_id,
            events=[event.model_dump() for event in payload.events],
        )
        return json_success()
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error saving assistant turn events")
        return json_error("Error saving assistant turn events", status_code=500)


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
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
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
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
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
    except exceptions_validation.JSONError as e:
        return json_error(str(e), status_code=e.status_code)
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
