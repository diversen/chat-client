import asyncio
from functools import wraps
import time
import json
import logging
import uuid
from typing import Any, cast

import data.config as config
from openai import OpenAI
from starlette.requests import Request

from chat_client.core import base_context
from chat_client.core import attachments as attachment_service
from chat_client.core import chat_service
from chat_client.core.chat_message_utils import (
    build_dialog_title_prompt as _build_dialog_title_prompt,
    build_model_messages_from_dialog_history as _build_model_messages_from_dialog_history,
    derive_dialog_title_from_user_message as _derive_dialog_title_from_user_message,
    extract_first_user_message as _extract_first_user_message,
    is_pending_dialog_title as _is_pending_dialog_title,
    normalize_chat_messages as _normalize_chat_messages,
    normalize_generated_dialog_title as _normalize_generated_dialog_title,
    strip_images_from_messages as _strip_images_from_messages,
)
from chat_client.core import config_utils
from chat_client.core import mcp_client
from chat_client.core import model_capabilities
from chat_client.core import tool_executor
from chat_client.core.usage_pricing import compute_usage_cost, normalize_chat_usage, resolve_model_pricing
from chat_client.endpoints import chat_attachment_endpoints, chat_dialog_endpoints, chat_page_endpoints, chat_stream_endpoints
from chat_client.repositories import attachment_repository, chat_repository, prompt_repository
from chat_client.core import exceptions_validation
from chat_client.core.http import (
    json_error,
    json_error_from_exception,
    json_success,
    get_user_id_or_redirect,
    parse_json_payload,
    require_user_id_json,
)
from chat_client.core.api_utils import get_ollama_model_metadata
from chat_client.schemas.chat import (
    ChatStreamRequest,
    CreateAssistantTurnEventsRequest,
    CreateDialogRequest,
    CreateMessageRequest,
    UpdateMessageRequest,
)

# Logger
logger: logging.Logger = logging.getLogger(__name__)

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
CONFIGURED_DIALOG_TITLE_MODEL = getattr(config, "DIALOG_TITLE_MODEL", "")
CONFIGURED_MODEL_PRICING = getattr(config, "MODEL_PRICING", {})
RESOLVED_CHAT_MAX_LOOP_ROUNDS = getattr(config, "CHAT_MAX_LOOP_ROUNDS", chat_service.DEFAULT_CHAT_MAX_LOOP_ROUNDS)
RESOLVED_CHAT_EMPTY_ANSWER_RETRY_COUNT = getattr(config, "CHAT_EMPTY_ANSWER_RETRY_COUNT", 1)
RESOLVED_CHAT_RETRY_ON_EMPTY_ANSWER_STOP = bool(getattr(config, "CHAT_RETRY_ON_EMPTY_ANSWER_STOP", False))

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
DIALOG_TITLE_MODEL = str(CONFIGURED_DIALOG_TITLE_MODEL or "").strip()
CHAT_MAX_LOOP_ROUNDS = RESOLVED_CHAT_MAX_LOOP_ROUNDS
MODEL_PRICING = CONFIGURED_MODEL_PRICING

_mcp_tools_cache: list[dict] = []
_mcp_tools_cache_at: float = 0.0


def _chat_login_redirect_path(request: Request, fallback: str = "/") -> str:
    next_path = str(request.query_params.get("next", "") or "").strip()
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path

    dialog_id = str(request.path_params.get("dialog_id", "") or "").strip()
    if not dialog_id:
        try:
            payload = request._json  # type: ignore[attr-defined]
        except AttributeError:
            payload = None
        if isinstance(payload, dict):
            dialog_id = str(payload.get("dialog_id", "") or "").strip()

    if dialog_id:
        return f"/chat/{dialog_id}"
    return fallback


def _json_error_with_auth_redirect(request: Request, error: exceptions_validation.JSONError, fallback: str = "/"):
    return json_error_from_exception(error, redirect_to=_chat_login_redirect_path(request, fallback=fallback))


def _with_auth_redirect_on_json_error(*, fallback: str = "/"):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            try:
                return await func(request, *args, **kwargs)
            except exceptions_validation.JSONError as error:
                return _json_error_with_auth_redirect(request, error, fallback=fallback)

        return wrapper

    return decorator


def _resolve_provider_info(model: str) -> dict:
    return chat_service.resolve_provider_info(model, MODELS, PROVIDERS)


def _resolve_provider_name(model: str) -> str:
    model_config = MODELS.get(model, "")
    if isinstance(model_config, str):
        return model_config
    if isinstance(model_config, dict):
        return str(model_config.get("provider", "") or "").strip()
    return ""


def _build_model_providers() -> dict[str, str]:
    return {
        str(model_name): _resolve_provider_name(str(model_name))
        for model_name in MODELS.keys()
    }


def _provider_supports_stream_usage(provider_name: str, provider_info: dict[str, Any]) -> bool:
    normalized_provider_name = str(provider_name or "").strip().lower()
    if normalized_provider_name == "openai":
        return True
    base_url = str(provider_info.get("base_url", "") or "").strip().lower()
    return base_url.startswith("https://api.openai.com/")


def _build_usage_cost_record(provider_name: str, model_name: str, usage_data: dict[str, Any]) -> dict[str, Any]:
    pricing = resolve_model_pricing(MODEL_PRICING, provider_name, model_name)
    input_tokens = int(usage_data.get("input_tokens", 0) or 0)
    cached_input_tokens = min(int(usage_data.get("cached_input_tokens", 0) or 0), input_tokens)
    output_tokens = int(usage_data.get("output_tokens", 0) or 0)
    total_tokens = int(usage_data.get("total_tokens", 0) or 0)
    reasoning_tokens = int(usage_data.get("reasoning_tokens", 0) or 0)
    return {
        "provider": provider_name,
        "model": model_name,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "input_price_per_million": pricing["input_per_million"],
        "cached_input_price_per_million": pricing["cached_input_per_million"],
        "output_price_per_million": pricing["output_per_million"],
        "currency": pricing["currency"],
        "cost_amount": compute_usage_cost(
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            input_per_million=pricing["input_per_million"],
            cached_input_per_million=pricing["cached_input_per_million"],
            output_per_million=pricing["output_per_million"],
        ),
    }


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


def _supports_model_thinking_control(model_name: str) -> bool:
    return model_capabilities.supports_model_thinking_control(
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
    return await chat_page_endpoints.chat_page(
        request,
        get_user_id_or_redirect=get_user_id_or_redirect,
        get_model_names=_get_model_names,
        list_prompts=prompt_repository.list_prompts,
        get_context=base_context.get_context,
        default_model=getattr(config, "DEFAULT_MODEL", ""),
        build_model_capabilities=_build_model_capabilities,
    )


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


TITLE_GENERATION_MAX_TOKENS = 24


def _generate_dialog_title(user_content: str, model: str, user_id: int | None = None, dialog_id: str = "") -> str:
    normalized_user_content = str(user_content or "").strip()
    selected_model = str(model or "").strip()
    if not normalized_user_content:
        raise exceptions_validation.UserValidate("User content is required to generate a dialog title")
    if not selected_model:
        raise exceptions_validation.UserValidate("Model is required to generate a dialog title")

    provider_info = _resolve_provider_info(selected_model)
    provider_name = _resolve_provider_name(selected_model)
    client = OpenAI(
        api_key=provider_info.get("api_key"),
        base_url=provider_info.get("base_url"),
    )
    response = client.chat.completions.create(
        model=selected_model,
        messages=cast(Any, _build_dialog_title_prompt(normalized_user_content)),
        stream=False,
        max_tokens=TITLE_GENERATION_MAX_TOKENS,
    )
    usage_data = normalize_chat_usage(response)
    usage_cost_record = _build_usage_cost_record(provider_name, selected_model, usage_data)
    if user_id is not None and dialog_id:
        asyncio.run(
            chat_repository.create_llm_usage_event(
                user_id=user_id,
                dialog_id=dialog_id,
                turn_id="",
                round_index=1,
                provider=usage_cost_record["provider"],
                model=usage_cost_record["model"],
                call_type="title_generation",
                request_id=usage_data["request_id"],
                input_tokens=usage_cost_record["input_tokens"],
                cached_input_tokens=usage_cost_record["cached_input_tokens"],
                output_tokens=usage_cost_record["output_tokens"],
                total_tokens=usage_cost_record["total_tokens"],
                reasoning_tokens=usage_cost_record["reasoning_tokens"],
                input_price_per_million=usage_cost_record["input_price_per_million"],
                cached_input_price_per_million=usage_cost_record["cached_input_price_per_million"],
                output_price_per_million=usage_cost_record["output_price_per_million"],
                currency=usage_cost_record["currency"],
                cost_amount=usage_cost_record["cost_amount"],
                usage_source=usage_data["usage_source"],
            )
        )
    _log_chat_event(
        logging.INFO,
        "chat.dialog_title.usage",
        model=selected_model,
        provider=provider_name,
        input_tokens=usage_data["input_tokens"],
        cached_input_tokens=usage_data["cached_input_tokens"],
        output_tokens=usage_data["output_tokens"],
        total_tokens=usage_data["total_tokens"],
        cost_amount=usage_cost_record["cost_amount"],
        currency=usage_cost_record["currency"],
        usage_source=usage_data["usage_source"],
    )
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        _log_chat_event(
            logging.INFO,
            "chat.dialog_title.raw",
            model=selected_model,
            raw_title="",
        )
        return _derive_dialog_title_from_user_message(normalized_user_content)
    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    raw_content = getattr(message, "content", "") if message is not None else ""
    _log_chat_event(
        logging.INFO,
        "chat.dialog_title.raw",
        model=selected_model,
        raw_title=str(raw_content or ""),
    )
    normalized_title = _normalize_generated_dialog_title(str(raw_content or ""))
    if _is_pending_dialog_title(normalized_title):
        return _derive_dialog_title_from_user_message(normalized_user_content)
    return normalized_title


async def _chat_response_stream(
    request: Request,
    messages,
    model,
    reasoning_effort,
    logged_in,
    dialog_id: str,
    trace_id: str,
    available_attachments: list[dict[str, Any]] | None = None,
):
    log_context = _build_chat_log_context(trace_id=trace_id, user_id=logged_in, dialog_id=dialog_id, model=model)
    tool_attachments = list(available_attachments or [])
    provider_name = _resolve_provider_name(model)
    provider_info = _resolve_provider_info(model)
    effective_reasoning_effort = reasoning_effort if _supports_model_thinking_control(model) else ""
    usage_turn_id = str(uuid.uuid4())

    async def _tool_executor_with_persist(tool_call):
        result_text = ""
        error_text = ""
        started_at = time.perf_counter()
        try:
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

    async def _persist_usage_event(**usage_data: Any) -> None:
        if not dialog_id:
            return
        usage_cost_record = _build_usage_cost_record(provider_name, model, usage_data)
        await chat_repository.create_llm_usage_event(
            user_id=logged_in,
            dialog_id=dialog_id,
            turn_id=str(usage_data.get("turn_id", "") or usage_turn_id),
            round_index=int(usage_data.get("round_index", 0) or 0),
            provider=usage_cost_record["provider"],
            model=usage_cost_record["model"],
            call_type=str(usage_data.get("call_type", "chat") or "chat"),
            request_id=str(usage_data.get("request_id", "") or ""),
            input_tokens=usage_cost_record["input_tokens"],
            cached_input_tokens=usage_cost_record["cached_input_tokens"],
            output_tokens=usage_cost_record["output_tokens"],
            total_tokens=usage_cost_record["total_tokens"],
            reasoning_tokens=usage_cost_record["reasoning_tokens"],
            input_price_per_million=usage_cost_record["input_price_per_million"],
            cached_input_price_per_million=usage_cost_record["cached_input_price_per_million"],
            output_price_per_million=usage_cost_record["output_price_per_million"],
            currency=usage_cost_record["currency"],
            cost_amount=usage_cost_record["cost_amount"],
            usage_source=str(usage_data.get("usage_source", "missing") or "missing"),
        )
        _log_chat_event(
            logging.INFO,
            "chat.usage.persisted",
            turn_id=str(usage_data.get("turn_id", "") or usage_turn_id),
            round_index=int(usage_data.get("round_index", 0) or 0),
            provider=provider_name,
            input_tokens=usage_cost_record["input_tokens"],
            cached_input_tokens=usage_cost_record["cached_input_tokens"],
            output_tokens=usage_cost_record["output_tokens"],
            total_tokens=usage_cost_record["total_tokens"],
            cost_amount=usage_cost_record["cost_amount"],
            currency=usage_cost_record["currency"],
            usage_source=str(usage_data.get("usage_source", "missing") or "missing"),
            **log_context,
        )

    yield f"data: {json.dumps({'turn_id': usage_turn_id})}\n\n"

    async for chunk in chat_service.chat_response_stream(
        request,
        messages,
        model,
        reasoning_effort=effective_reasoning_effort,
        openai_client_cls=OpenAI,
        provider_info_resolver=_resolve_provider_info,
        tool_models=_resolve_tool_models(),
        tools_loader=_list_tools,
        tool_executor=_tool_executor_with_persist,
        max_chat_loop_rounds=CHAT_MAX_LOOP_ROUNDS,
        empty_answer_retry_count=RESOLVED_CHAT_EMPTY_ANSWER_RETRY_COUNT,
        retry_on_empty_answer_stop=RESOLVED_CHAT_RETRY_ON_EMPTY_ANSWER_STOP,
        logger=logger,
        trace_id=trace_id,
        user_id=logged_in,
        dialog_id=dialog_id,
        turn_id=usage_turn_id,
        provider_name=provider_name,
        include_usage_in_stream=_provider_supports_stream_usage(provider_name, provider_info),
        persist_usage_event=_persist_usage_event,
    ):
        yield chunk


async def stream_chat(request: Request):
    return await chat_stream_endpoints.chat_response_stream(
        request,
        require_user_id_json=require_user_id_json,
        parse_json_payload=parse_json_payload,
        chat_stream_request=ChatStreamRequest,
        new_trace_id=_new_trace_id,
        build_chat_log_context=_build_chat_log_context,
        log_chat_event=_log_chat_event,
        summarize_messages_for_log=chat_service.summarize_messages_for_log,
        summarize_last_user_message_for_log=chat_service.summarize_last_user_message_for_log,
        get_dialog=chat_repository.get_dialog,
        get_messages=chat_repository.get_messages,
        build_model_messages_from_dialog_history=_build_model_messages_from_dialog_history,
        get_attachments=attachment_repository.get_attachments,
        supports_model_images=_supports_model_images,
        strip_images_from_messages=_strip_images_from_messages,
        normalize_chat_messages=_normalize_chat_messages,
        stream_response_fn=_chat_response_stream,
        json_error_from_exception=json_error_from_exception,
        chat_login_redirect_path=_chat_login_redirect_path,
    )


@_with_auth_redirect_on_json_error()
async def get_dialog_usage(request: Request):
    return await chat_dialog_endpoints.get_dialog_usage(
        request,
        require_user_id_json=require_user_id_json,
        chat_repository=chat_repository,
        exceptions_validation=exceptions_validation,
        json_success=json_success,
        json_error=json_error,
        logger=logger,
    )


@_with_auth_redirect_on_json_error()
async def upload_attachment(request: Request):
    return await chat_attachment_endpoints.upload_attachment(
        request,
        require_user_id_json=require_user_id_json,
        get_dialog=chat_repository.get_dialog,
        get_messages=chat_repository.get_messages,
        attachment_service=attachment_service,
        attachment_repository=attachment_repository,
        exceptions_validation=exceptions_validation,
        json_success=json_success,
        json_error=json_error,
        logger=logger,
    )


async def preview_attachment(request: Request):
    return await chat_attachment_endpoints.preview_attachment(
        request,
        get_user_id_or_redirect=get_user_id_or_redirect,
        attachment_repository=attachment_repository,
        exceptions_validation=exceptions_validation,
        json_error=json_error,
        attachment_preview_is_image=_attachment_preview_is_image,
        attachment_preview_is_text=_attachment_preview_is_text,
        logger=logger,
    )


async def get_chat_config(request: Request):
    return await chat_page_endpoints.get_chat_config(
        request,
        frontend_config_impl=chat_dialog_endpoints.get_chat_config,
        config=config,
        system_message_denylist=SYSTEM_MESSAGE_DENYLIST,
        vision_models=VISION_MODELS,
        build_model_capabilities=_build_model_capabilities,
        build_model_providers=_build_model_providers,
        json_success=json_success,
    )


async def _get_model_names():
    return list(MODELS.keys())


async def _get_model_entries():
    entries: list[dict[str, Any]] = []
    for model_name in MODELS.keys():
        entry: dict[str, Any] = {"name": model_name}
        if model_capabilities.resolve_model_provider_name(MODELS, model_name) == "ollama":
            metadata = get_ollama_model_metadata(_resolve_provider_info(model_name), model_name)
            if metadata.get("context_length") is not None:
                entry["context_length"] = metadata["context_length"]
        entries.append(entry)
    return entries


async def list_chat_models(request: Request):
    return await chat_page_endpoints.list_chat_models(
        request,
        list_models_impl=chat_dialog_endpoints.list_chat_models,
        get_model_names=_get_model_names,
        get_model_entries=_get_model_entries,
        json_success=json_success,
    )


@_with_auth_redirect_on_json_error()
async def create_dialog(request: Request):
    return await chat_dialog_endpoints.create_dialog(
        request,
        require_user_id_json=require_user_id_json,
        parse_json_payload=parse_json_payload,
        create_dialog_request=CreateDialogRequest,
        chat_repository=chat_repository,
        is_pending_dialog_title=_is_pending_dialog_title,
        derive_dialog_title_from_user_message=_derive_dialog_title_from_user_message,
        exceptions_validation=exceptions_validation,
        json_success=json_success,
        json_error=json_error,
        logger=logger,
    )


@_with_auth_redirect_on_json_error()
async def create_message(request: Request):
    return await chat_dialog_endpoints.create_message(
        request,
        require_user_id_json=require_user_id_json,
        parse_json_payload=parse_json_payload,
        create_message_request=CreateMessageRequest,
        attachment_repository=attachment_repository,
        chat_repository=chat_repository,
        supports_model_images=_supports_model_images,
        supports_model_attachments=_supports_model_attachments,
        image_modality_error_message=chat_service.IMAGE_MODALITY_ERROR_MESSAGE,
        exceptions_validation=exceptions_validation,
        json_success=json_success,
        json_error=json_error,
        logger=logger,
    )


@_with_auth_redirect_on_json_error()
async def create_dialog_title(request: Request):
    return await chat_dialog_endpoints.create_dialog_title(
        request,
        require_user_id_json=require_user_id_json,
        chat_repository=chat_repository,
        dialog_title_model=DIALOG_TITLE_MODEL,
        is_pending_dialog_title=_is_pending_dialog_title,
        extract_first_user_message=_extract_first_user_message,
        create_dialog_title_fn=_generate_dialog_title,
        derive_dialog_title_from_user_message=_derive_dialog_title_from_user_message,
        log_chat_event=_log_chat_event,
        exceptions_validation=exceptions_validation,
        json_success=json_success,
        json_error=json_error,
        logger=logger,
    )


@_with_auth_redirect_on_json_error()
async def create_assistant_turn_events(request: Request):
    return await chat_dialog_endpoints.create_assistant_turn_events(
        request,
        require_user_id_json=require_user_id_json,
        parse_json_payload=parse_json_payload,
        create_assistant_turn_events_request=CreateAssistantTurnEventsRequest,
        chat_repository=chat_repository,
        exceptions_validation=exceptions_validation,
        json_success=json_success,
        json_error=json_error,
        logger=logger,
    )


@_with_auth_redirect_on_json_error()
async def get_dialog(request: Request):
    return await chat_dialog_endpoints.get_dialog(
        request,
        require_user_id_json=require_user_id_json,
        chat_repository=chat_repository,
        exceptions_validation=exceptions_validation,
        json_error=json_error,
        logger=logger,
    )


@_with_auth_redirect_on_json_error()
async def list_messages(request: Request):
    return await chat_dialog_endpoints.list_messages(
        request,
        require_user_id_json=require_user_id_json,
        chat_repository=chat_repository,
        exceptions_validation=exceptions_validation,
        json_error=json_error,
        logger=logger,
    )


@_with_auth_redirect_on_json_error()
async def delete_dialog(request: Request):
    return await chat_dialog_endpoints.delete_dialog(
        request,
        require_user_id_json=require_user_id_json,
        chat_repository=chat_repository,
        exceptions_validation=exceptions_validation,
        json_success=json_success,
        json_error=json_error,
        logger=logger,
    )


@_with_auth_redirect_on_json_error()
async def update_message(request: Request):
    return await chat_dialog_endpoints.update_message(
        request,
        require_user_id_json=require_user_id_json,
        parse_json_payload=parse_json_payload,
        update_message_request=UpdateMessageRequest,
        chat_repository=chat_repository,
        derive_dialog_title_from_user_message=_derive_dialog_title_from_user_message,
        exceptions_validation=exceptions_validation,
        json_success=json_success,
        json_error=json_error,
        logger=logger,
    )
