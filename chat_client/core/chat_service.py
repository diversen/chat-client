import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from inspect import isawaitable, iscoroutinefunction
from typing import Any

from openai import OpenAIError
from starlette.requests import Request

from chat_client.core.attachments import (
    attachment_to_image_data_url,
    format_attachment_note,
    list_attachment_paths,
    parse_image_attachment_ref,
)
from chat_client.core.usage_pricing import normalize_usage_payload

GENERIC_OPENAI_ERROR_MESSAGE = "An error occurred. Please try again later."
IMAGE_MODALITY_ERROR_MESSAGE = "The selected model does not support image inputs. Remove attached images or choose a vision model."
TOOL_ROUTER_MAX_TOKENS = 64
DEFAULT_CHAT_MAX_LOOP_ROUNDS = 8
GENERIC_LOG_TEXT_PREVIEW_LIMIT = 256
ASSISTANT_LOG_TEXT_PREVIEW_LIMIT = 64
TOOL_ARGUMENTS_LOG_TEXT_PREVIEW_LIMIT = 64
TOOL_RESULT_LOG_TEXT_PREVIEW_LIMIT = 128
THINKING_TAG_PATTERN = re.compile(r"</?(?:think|thinking|thought)>", re.IGNORECASE)
INCOMPLETE_STREAM_ERROR_MESSAGE = "The model ended the stream without producing an answer. Please try again."


class ToolExecutionError(Exception):
    """
    Base error for tool parsing, routing, and execution failures.
    """


class ToolNotConfiguredError(ToolExecutionError):
    """
    Raised when no tool backend is configured.
    """


class ToolNotFoundError(ToolExecutionError):
    """
    Raised when a named tool cannot be found.
    """


class ToolArgumentsError(ToolExecutionError):
    """
    Raised when tool arguments are invalid or do not match the schema.
    """


class ToolBackendError(ToolExecutionError):
    """
    Raised when a backend fails while executing a tool.
    """


class IncompleteStreamError(Exception):
    """
    Raised when the provider ends a stream without a terminal result.
    """


def _truncate_for_log(value: Any, limit: int = GENERIC_LOG_TEXT_PREVIEW_LIMIT) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {key: value for key, value in fields.items() if value is not None}
    logger.log(level, "%s: %s", event, payload)


def _count_message_images(message: dict[str, Any]) -> int:
    images = message.get("images", [])
    if isinstance(images, list):
        return len(images)

    content = message.get("content", [])
    if not isinstance(content, list):
        return 0
    return sum(1 for item in content if isinstance(item, dict) and item.get("type") == "image_url")


def _count_message_attachments(message: dict[str, Any]) -> int:
    attachments = message.get("attachments", [])
    if isinstance(attachments, list):
        return len(attachments)
    return 0


def summarize_messages_for_log(messages: list[dict[str, Any]]) -> dict[str, Any]:
    role_counts: dict[str, int] = {}
    image_count = 0
    attachment_count = 0
    attachment_paths: list[str] = []
    tool_call_count = 0
    text_chars = 0

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).strip() or "unknown"
        role_counts[role] = role_counts.get(role, 0) + 1
        image_count += _count_message_images(message)
        attachment_count += _count_message_attachments(message)
        if role == "user":
            attachment_paths.extend(list_attachment_paths(message.get("attachments", [])))
        tool_calls = message.get("tool_calls", [])
        if isinstance(tool_calls, list):
            tool_call_count += len(tool_calls)
        content = message.get("content", "")
        if isinstance(content, str):
            text_chars += len(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_chars += len(str(item.get("text", "")))

    summary = {
        "message_count": len(messages),
        "role_counts": role_counts,
        "image_count": image_count,
        "attachment_count": attachment_count,
        "tool_call_count": tool_call_count,
        "text_chars": text_chars,
    }
    if attachment_paths:
        summary["attachment_paths"] = sorted(set(attachment_paths))
    return summary


def summarize_last_user_message_for_log(messages: list[dict[str, Any]]) -> dict[str, Any]:
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if str(message.get("role", "")).strip() != "user":
            continue

        content = message.get("content", "")
        if isinstance(content, str):
            return {
                "last_user_message_full": content,
            }

        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
                elif item.get("type") == "image_url":
                    text_parts.append("[image]")
            return {
                "last_user_message_full": "\n".join(part for part in text_parts if part),
            }

    return {}


def _split_thinking_and_answer_text(content: str) -> tuple[str, str]:
    if not content:
        return "", ""

    parts = THINKING_TAG_PATTERN.split(content)
    tags = THINKING_TAG_PATTERN.findall(content)
    is_thinking = False
    thinking_parts: list[str] = []
    answer_parts: list[str] = []

    for index, part in enumerate(parts):
        if part:
            if is_thinking:
                thinking_parts.append(part)
            else:
                answer_parts.append(part)
        if index < len(tags):
            tag = tags[index]
            is_thinking = not tag.startswith("</")

    return "".join(thinking_parts), "".join(answer_parts)


def summarize_assistant_text_for_log(content: str) -> dict[str, Any]:
    thinking_text, answer_text = _split_thinking_and_answer_text(content)
    return {
        "content_chars": len(content),
        "thinking_chars": len(thinking_text),
        "answer_chars": len(answer_text),
        "thinking_preview": _truncate_for_log(thinking_text, ASSISTANT_LOG_TEXT_PREVIEW_LIMIT),
        "answer_preview": _truncate_for_log(answer_text, ASSISTANT_LOG_TEXT_PREVIEW_LIMIT),
        "has_thinking": bool(thinking_text),
    }


def summarize_tool_call_for_log(tool_call: dict[str, Any]) -> dict[str, Any]:
    function = tool_call.get("function", {})
    name = str(function.get("name", "")).strip() if isinstance(function, dict) else ""
    arguments = function.get("arguments", "{}") if isinstance(function, dict) else "{}"
    return {
        "tool_call_id": str(tool_call.get("id", "")).strip(),
        "tool_name": name,
        "arguments_preview": _truncate_for_log(arguments, TOOL_ARGUMENTS_LOG_TEXT_PREVIEW_LIMIT),
    }


def summarize_tool_result_for_log(tool_call: dict[str, Any], result_text: str, error_text: str) -> dict[str, Any]:
    summary = summarize_tool_call_for_log(tool_call)
    summary.update(
        {
            "status": "error" if error_text else "ok",
            "result_preview": _truncate_for_log(result_text, TOOL_RESULT_LOG_TEXT_PREVIEW_LIMIT),
            "error_preview": _truncate_for_log(error_text, TOOL_RESULT_LOG_TEXT_PREVIEW_LIMIT),
            "result_chars": len(result_text),
            "error_chars": len(error_text),
        }
    )
    return summary


def _summarize_chunk_for_log(model_dict: dict[str, Any]) -> dict[str, Any]:
    choices = model_dict.get("choices", [])
    first_choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    delta = first_choice.get("delta", {}) if isinstance(first_choice, dict) else {}
    delta_keys = sorted(delta.keys()) if isinstance(delta, dict) else []
    return {
        "top_level_keys": sorted(model_dict.keys()),
        "choice_count": len(choices) if isinstance(choices, list) else 0,
        "delta_keys": delta_keys,
        "finish_reason": first_choice.get("finish_reason", "") if isinstance(first_choice, dict) else "",
    }


def _close_stream(stream: Any, logger: logging.Logger) -> None:
    """
    Best-effort close of an OpenAI stream-like object.
    """
    close = getattr(stream, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        logger.exception("Failed to close provider stream")


def _create_sync_stream(create_fn: Callable[..., Any], create_kwargs: dict[str, Any]) -> Any:
    """
    Run the provider stream creation in a worker thread so connection setup
    cannot block the event loop.
    """
    return create_fn(**create_kwargs)


def _next_stream_chunk(iterator: Any) -> tuple[bool, Any]:
    """
    Advance a synchronous stream iterator without leaking StopIteration across
    the thread boundary.
    """
    try:
        return False, next(iterator)
    except StopIteration:
        return True, None


def _extract_error_messages(value: Any) -> list[str]:
    messages: list[str] = []
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str) and message.strip():
            messages.append(message.strip())
        nested = value.get("error")
        if nested is not None:
            messages.extend(_extract_error_messages(nested))
    elif isinstance(value, list):
        for item in value:
            messages.extend(_extract_error_messages(item))
    elif isinstance(value, str) and value.strip():
        messages.append(value.strip())
    return messages


def map_openai_error_message(error: OpenAIError) -> str:
    texts: list[str] = []

    direct_message = str(error).strip()
    if direct_message:
        texts.append(direct_message)

    error_body = getattr(error, "body", None)
    if error_body is not None:
        texts.extend(_extract_error_messages(error_body))

    response = getattr(error, "response", None)
    if response is not None:
        try:
            texts.extend(_extract_error_messages(response.json()))
        except Exception:
            pass

    joined = " ".join(texts).lower()
    if "image input modality is not enabled" in joined or "image modality" in joined or "does not support image" in joined:
        return IMAGE_MODALITY_ERROR_MESSAGE

    return GENERIC_OPENAI_ERROR_MESSAGE


def resolve_provider_info(model: str, models: dict[str, Any], providers: dict[str, Any]) -> dict[str, Any]:
    model_config = models.get(model, "")

    if isinstance(model_config, str):
        return providers.get(model_config, {})

    if isinstance(model_config, dict):
        provider_name = model_config.get("provider")
        base_info = providers.get(provider_name, {}) if isinstance(provider_name, str) else {}
        merged = {**base_info, **model_config}
        merged.pop("provider", None)
        return merged

    return {}


def normalize_chat_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """
    Convert user messages with uploaded images into OpenAI content parts.
    """
    normalized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue

        role = str(message.get("role", ""))
        if role != "user":
            normalized.append(message)
            continue

        normalized.append(build_normalized_user_message(message))

    return normalized


def build_user_message_text(message: dict[str, Any]) -> str:
    content = str(message.get("content", ""))
    attachment_note = format_attachment_note(message.get("attachments", []))
    if attachment_note:
        content = f"{content}\n\n{attachment_note}".strip()
    return content


def build_normalized_user_message(message: dict[str, Any]) -> dict[str, Any]:
    content = build_user_message_text(message)
    images = message.get("images", [])
    if not isinstance(images, list) or not images:
        return {**message, "content": content}

    content_parts: list[dict[str, Any]] = []
    if content:
        content_parts.append({"type": "text", "text": content})

    for image in images:
        if not isinstance(image, dict):
            continue
        data_url = str(image.get("data_url", "")).strip()
        attachment_id = image.get("attachment_id")
        if not data_url and isinstance(attachment_id, (str, int)):
            try:
                normalized_attachment_id = int(attachment_id)
            except (TypeError, ValueError):
                normalized_attachment_id = 0
            if normalized_attachment_id > 0:
                data_url = attachment_to_image_data_url(
                    {
                        "attachment_id": normalized_attachment_id,
                        "content_type": str(image.get("content_type", "") or ""),
                        "storage_path": str(image.get("storage_path", "") or ""),
                    }
                )
        else:
            image_attachment_id = parse_image_attachment_ref(data_url)
            if image_attachment_id is not None:
                data_url = attachment_to_image_data_url(image)
        if not data_url.startswith("data:image/"):
            continue
        content_parts.append(
            {
                "type": "image_url",
                "image_url": {"url": data_url},
            }
        )

    if content_parts:
        return {"role": "user", "content": content_parts}
    return {"role": "user", "content": content}


def has_image_inputs(messages: list[Any]) -> bool:
    """
    Check whether any user message includes attached images.
    """
    for message in messages:
        if not isinstance(message, dict):
            continue
        if str(message.get("role", "")) != "user":
            continue
        images = message.get("images", [])
        if isinstance(images, list) and len(images) > 0:
            return True
    return False


def execute_tool(
    tool_call: dict[str, Any],
    tool_registry: dict[str, Callable[..., Any]],
    logger: logging.Logger,
    *,
    log_context: dict[str, Any] | None = None,
) -> Any:
    """
    Execute a model tool call from the configured registry.
    """
    func_name = str(tool_call.get("function", {}).get("name", "")).strip()
    args = parse_tool_arguments(tool_call, logger)
    _log_event(
        logger,
        logging.INFO,
        "chat.tool.local.start",
        tool_name=func_name,
        arguments_preview=_truncate_for_log(
            json.dumps(args, ensure_ascii=True, sort_keys=True),
            TOOL_ARGUMENTS_LOG_TEXT_PREVIEW_LIMIT,
        ),
        **(log_context or {}),
    )

    if func_name not in tool_registry:
        raise ToolNotFoundError(f'Tool "{func_name}" does not exist.')

    try:
        return tool_registry[func_name](**args)
    except TypeError as error:
        raise ToolArgumentsError(f'Tool "{func_name}" was called with invalid arguments: {error}') from error
    except ToolExecutionError:
        raise
    except Exception as error:
        raise ToolBackendError(f'Tool "{func_name}" failed: {error}') from error


async def execute_tool_nonblocking(
    tool_call: dict[str, Any],
    tool_executor: Callable[[dict[str, Any]], Any],
) -> Any:
    """
    Run sync tool executors off the event loop while awaiting async ones directly.
    """
    if iscoroutinefunction(tool_executor):
        return await tool_executor(tool_call)

    result = await asyncio.to_thread(tool_executor, tool_call)
    if isawaitable(result):
        return await result
    return result


def parse_tool_arguments(tool_call: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    func_name = str(tool_call.get("function", {}).get("name", "")).strip() or "unknown"
    raw_args = tool_call.get("function", {}).get("arguments", "{}")
    if not isinstance(raw_args, str):
        raise ToolArgumentsError(f'Tool "{func_name}" was called with invalid JSON arguments.')
    try:
        parsed = json.loads(raw_args)
    except json.JSONDecodeError as error:
        logger.exception("Invalid tool call arguments JSON")
        raise ToolArgumentsError(f'Tool "{func_name}" was called with invalid JSON arguments.') from error
    if isinstance(parsed, dict):
        return parsed
    raise ToolArgumentsError(f'Tool "{func_name}" requires JSON object arguments.')


def validate_tool_arguments(args: dict[str, Any], schema: dict[str, Any] | None, tool_name: str) -> None:
    if not schema:
        return

    schema_type = schema.get("type")
    if schema_type and schema_type != "object":
        raise ToolArgumentsError(f'Tool "{tool_name}" uses an unsupported argument schema.')

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}

    required = schema.get("required", [])
    if not isinstance(required, list):
        required = []

    for required_name in required:
        if isinstance(required_name, str) and required_name not in args:
            raise ToolArgumentsError(f'Tool "{tool_name}" requires argument "{required_name}".')

    additional_properties = schema.get("additionalProperties", True)
    if additional_properties is False:
        unexpected_names = sorted(name for name in args if name not in properties)
        if unexpected_names:
            formatted_names = ", ".join(f'"{name}"' for name in unexpected_names)
            raise ToolArgumentsError(f'Tool "{tool_name}" received unexpected arguments: {formatted_names}.')

    for arg_name, arg_value in args.items():
        if arg_name not in properties:
            continue
        property_schema = properties.get(arg_name)
        if not isinstance(property_schema, dict):
            continue
        expected_type = property_schema.get("type")
        if not isinstance(expected_type, str):
            continue
        if not _is_valid_tool_argument_type(arg_value, expected_type):
            raise ToolArgumentsError(f'Tool "{tool_name}" requires argument "{arg_name}" of type {expected_type}.')


def _is_valid_tool_argument_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "null":
        return value is None
    return True


def _resolve_max_chat_loop_rounds(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CHAT_MAX_LOOP_ROUNDS
    if resolved < 1:
        return DEFAULT_CHAT_MAX_LOOP_ROUNDS
    return resolved


def _resolve_empty_answer_retry_count(value: Any) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return 0
    return max(resolved, 0)


def normalize_reasoning_effort(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"low", "medium", "high"}:
        return normalized
    return ""


def _normalize_tool_calls(raw_tool_calls: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(raw_tool_calls, list):
        return normalized

    for index, raw_call in enumerate(raw_tool_calls):
        function = getattr(raw_call, "function", None)
        name = str(getattr(function, "name", "") or "").strip()
        if not name:
            continue

        arguments = getattr(function, "arguments", "{}")
        if not isinstance(arguments, str):
            arguments = "{}"

        call_id = getattr(raw_call, "id", None)
        if not isinstance(call_id, str) or not call_id.strip():
            call_id = f"tool_call_{index}"

        call_type = getattr(raw_call, "type", None)
        if not isinstance(call_type, str) or not call_type.strip():
            call_type = "function"

        normalized.append(
            {
                "id": call_id,
                "type": call_type,
                "function": {
                    "name": name,
                    "arguments": arguments,
                },
            }
        )

    return normalized


def _append_stream_tool_call_deltas(raw_tool_calls: Any, state: dict[str, Any]) -> None:
    """
    Merge streamed tool_call deltas into a stable list keyed by tool_call id.
    """
    if not isinstance(raw_tool_calls, list):
        return

    tool_calls_by_key: dict[str, dict[str, Any]] = state["tool_calls_by_key"]
    tool_call_order: list[str] = state["tool_call_order"]
    index_active_key: dict[int, str] = state["index_active_key"]

    for raw_call in raw_tool_calls:
        index = getattr(raw_call, "index", None)
        if not isinstance(index, int):
            index = -1

        call_id = getattr(raw_call, "id", None)
        if isinstance(call_id, str) and call_id.strip():
            key = call_id
            previous_key = index_active_key.get(index)
            if previous_key and previous_key.startswith("tmp:") and previous_key in tool_calls_by_key and key not in tool_calls_by_key:
                migrated = tool_calls_by_key.pop(previous_key)
                for i, candidate_key in enumerate(tool_call_order):
                    if candidate_key == previous_key:
                        tool_call_order[i] = key
                        break
                migrated["id"] = key
                tool_calls_by_key[key] = migrated
            index_active_key[index] = key
        else:
            key = index_active_key.get(index, "")
            if not key or key not in tool_calls_by_key:
                state["tmp_counter"] += 1
                key = f"tmp:{index}:{state['tmp_counter']}"
                index_active_key[index] = key

        if key not in tool_calls_by_key:
            tool_calls_by_key[key] = {
                "id": call_id if isinstance(call_id, str) and call_id.strip() else key,
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }
            tool_call_order.append(key)

        entry = tool_calls_by_key[key]
        if isinstance(call_id, str) and call_id.strip():
            entry["id"] = call_id

        call_type = getattr(raw_call, "type", None)
        if isinstance(call_type, str) and call_type.strip():
            entry["type"] = call_type

        function = getattr(raw_call, "function", None)
        if function is None:
            continue

        name = getattr(function, "name", None)
        if isinstance(name, str) and name.strip():
            entry["function"]["name"] = name

        arguments = getattr(function, "arguments", None)
        if isinstance(arguments, str) and arguments:
            entry["function"]["arguments"] += arguments


def _collect_streamed_tool_calls(state: dict[str, Any]) -> list[dict[str, Any]]:
    tool_calls_by_key: dict[str, dict[str, Any]] = state["tool_calls_by_key"]
    tool_call_order: list[str] = state["tool_call_order"]
    collected: list[dict[str, Any]] = []

    for key in tool_call_order:
        call = tool_calls_by_key.get(key)
        if not isinstance(call, dict):
            continue
        function = call.get("function", {})
        name = function.get("name", "") if isinstance(function, dict) else ""
        if not isinstance(name, str) or not name.strip():
            continue
        call_id = call.get("id", key)
        if not isinstance(call_id, str) or not call_id.strip():
            call_id = key
        arguments = function.get("arguments", "{}")
        if not isinstance(arguments, str):
            arguments = "{}"
        call_type = call.get("type", "function")
        if not isinstance(call_type, str) or not call_type.strip():
            call_type = "function"
        collected.append(
            {
                "id": call_id,
                "type": call_type,
                "function": {
                    "name": name.strip(),
                    "arguments": arguments,
                },
            }
        )
    return collected


def _summarize_assistant_message_for_log(assistant_message: Any, finish_reason: Any) -> dict[str, Any]:
    content = str(getattr(assistant_message, "content", "") or "")
    summary: dict[str, Any] = {
        "finish_reason": str(finish_reason or ""),
        "content": content,
    }
    tool_calls = _normalize_tool_calls(getattr(assistant_message, "tool_calls", None))
    if tool_calls:
        summary["tool_calls"] = tool_calls
    return summary


async def chat_response_stream(
    request: Request,
    messages: list[dict[str, Any]],
    model: str,
    reasoning_effort: str = "",
    *,
    openai_client_cls: Callable[..., Any],
    provider_info_resolver: Callable[[str], dict[str, Any]],
    tool_models: list[str],
    tools_loader: Callable[[], list[dict[str, Any]]],
    tool_executor: Callable[[dict[str, Any]], Any],
    max_chat_loop_rounds: int = DEFAULT_CHAT_MAX_LOOP_ROUNDS,
    empty_answer_retry_count: int = 0,
    retry_on_empty_answer_stop: bool = False,
    logger: logging.Logger,
    trace_id: str = "",
    user_id: Any = None,
    dialog_id: str = "",
    turn_id: str = "",
    provider_name: str = "",
    include_usage_in_stream: bool = False,
    persist_usage_event: Callable[..., Any] | None = None,
) -> AsyncIterator[str]:
    base_log_context = {
        "trace_id": trace_id,
        "user_id": user_id,
        "dialog_id": dialog_id,
        "model": model,
    }
    try:
        provider_info = provider_info_resolver(model)
        normalized_reasoning_effort = normalize_reasoning_effort(reasoning_effort)
        max_rounds = _resolve_max_chat_loop_rounds(max_chat_loop_rounds)
        max_empty_answer_retries = _resolve_empty_answer_retry_count(empty_answer_retry_count)

        _log_event(
            logger,
            logging.INFO,
            "chat.model.session.start",
            max_rounds=max_rounds,
            empty_answer_retry_count=max_empty_answer_retries,
            retry_on_empty_answer_stop=retry_on_empty_answer_stop,
            tools_enabled=model in tool_models,
            **summarize_messages_for_log(messages),
            **base_log_context,
        )

        client = openai_client_cls(
            api_key=provider_info.get("api_key"),
            base_url=provider_info.get("base_url"),
        )

        tools_enabled = model in tool_models
        tool_definitions = tools_loader() if tools_enabled else []
        empty_answer_retry_attempts = 0

        rounds = 0
        while True:
            rounds += 1
            if rounds > max_rounds:
                _log_event(
                    logger,
                    logging.WARNING,
                    "chat.model.loop_limit_exceeded",
                    round=rounds,
                    max_rounds=max_rounds,
                    **base_log_context,
                )
                yield f"data: {json.dumps({'error': 'Tool loop exceeded maximum rounds'})}\n\n"
                return

            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
            }
            if normalized_reasoning_effort and str(provider_name or "").strip().lower() == "openai":
                create_kwargs["reasoning_effort"] = normalized_reasoning_effort
            if include_usage_in_stream:
                create_kwargs["stream_options"] = {"include_usage": True}
            if tools_enabled:
                create_kwargs["tools"] = tool_definitions

            round_started_at = time.perf_counter()
            _log_event(
                logger,
                logging.INFO,
                "chat.model.call.start",
                round=rounds,
                tools_enabled=tools_enabled,
                tool_definition_count=len(tool_definitions),
                **summarize_messages_for_log(messages),
                **base_log_context,
            )

            stream_response = await asyncio.to_thread(_create_sync_stream, client.chat.completions.create, create_kwargs)
            disconnected = False
            assistant_content_parts: list[str] = []
            finish_reason: Any = None
            chunk_count = 0
            chunks_with_choices = 0
            chunks_with_delta = 0
            chunks_with_content = 0
            chunks_with_tool_calls = 0
            unknown_delta_keys: set[str] = set()
            first_chunk_summary: dict[str, Any] | None = None
            last_chunk_summary: dict[str, Any] | None = None
            first_chunk_preview = ""
            last_chunk_preview = ""
            usage_summary = {
                "request_id": "",
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
                "usage_source": "missing",
            }
            tool_call_state: dict[str, Any] = {
                "tool_calls_by_key": {},
                "tool_call_order": [],
                "index_active_key": {},
                "tmp_counter": 0,
            }

            try:
                stream_iterator = iter(stream_response)
                while True:
                    finished, chunk = await asyncio.to_thread(_next_stream_chunk, stream_iterator)
                    if finished:
                        break
                    if await request.is_disconnected():
                        disconnected = True
                        break

                    model_dict = chunk.model_dump()
                    chunk_count += 1
                    chunk_preview = _truncate_for_log(json.dumps(model_dict, ensure_ascii=True))
                    chunk_summary = _summarize_chunk_for_log(model_dict)
                    if first_chunk_summary is None:
                        first_chunk_summary = chunk_summary
                        first_chunk_preview = chunk_preview
                    last_chunk_summary = chunk_summary
                    last_chunk_preview = chunk_preview
                    json_chunk = json.dumps(model_dict)
                    yield f"data: {json_chunk}\n\n"
                    if isinstance(model_dict.get("usage"), dict):
                        usage_summary = normalize_usage_payload(model_dict)

                    choices = getattr(chunk, "choices", None)
                    if not isinstance(choices, list) or not choices:
                        continue
                    chunks_with_choices += 1
                    first_choice = choices[0]
                    delta = getattr(first_choice, "delta", None)
                    if delta is not None:
                        chunks_with_delta += 1
                        content_piece = getattr(delta, "content", None)
                        if isinstance(content_piece, str) and content_piece:
                            assistant_content_parts.append(content_piece)
                            chunks_with_content += 1
                        _append_stream_tool_call_deltas(getattr(delta, "tool_calls", None), tool_call_state)
                        if isinstance(getattr(delta, "tool_calls", None), list) and getattr(delta, "tool_calls", None):
                            chunks_with_tool_calls += 1
                        if hasattr(delta, "model_fields_set") and isinstance(delta.model_fields_set, set):
                            unknown_delta_keys.update(
                                str(key) for key in delta.model_fields_set if str(key) not in {"content", "tool_calls", "role", "refusal"}
                            )
                    if getattr(first_choice, "finish_reason", None) is not None:
                        finish_reason = getattr(first_choice, "finish_reason", None)
            finally:
                _close_stream(stream_response, logger)

            if disconnected:
                _log_event(
                    logger,
                    logging.INFO,
                    "chat.stream.client_disconnected",
                    round=rounds,
                    duration_ms=round((time.perf_counter() - round_started_at) * 1000, 2),
                    **base_log_context,
                )
                return

            tool_calls = _collect_streamed_tool_calls(tool_call_state)
            if tool_calls and not tools_enabled:
                _log_event(
                    logger,
                    logging.WARNING,
                    "chat.model.unexpected_tool_calls_ignored",
                    round=rounds,
                    tool_calls=[summarize_tool_call_for_log(tool_call) for tool_call in tool_calls],
                    **base_log_context,
                )
                tool_calls = []
            assistant_content = "".join(assistant_content_parts)
            assistant_summary = summarize_assistant_text_for_log(assistant_content)
            _log_event(
                logger,
                logging.INFO,
                "chat.model.call.finish",
                round=rounds,
                finish_reason=str(finish_reason or ""),
                duration_ms=round((time.perf_counter() - round_started_at) * 1000, 2),
                tool_call_count=len(tool_calls),
                content_chars=assistant_summary["content_chars"],
                chunk_count=chunk_count,
                usage_source=usage_summary["usage_source"],
                input_tokens=usage_summary["input_tokens"],
                cached_input_tokens=usage_summary["cached_input_tokens"],
                output_tokens=usage_summary["output_tokens"],
                total_tokens=usage_summary["total_tokens"],
                **base_log_context,
            )
            if persist_usage_event is not None:
                persist_result = persist_usage_event(
                    turn_id=turn_id,
                    round_index=rounds,
                    provider=provider_name,
                    model=model,
                    call_type="chat",
                    request_id=usage_summary["request_id"],
                    input_tokens=usage_summary["input_tokens"],
                    cached_input_tokens=usage_summary["cached_input_tokens"],
                    output_tokens=usage_summary["output_tokens"],
                    total_tokens=usage_summary["total_tokens"],
                    reasoning_tokens=usage_summary["reasoning_tokens"],
                    usage_source=usage_summary["usage_source"],
                )
                if isawaitable(persist_result):
                    await persist_result
            _log_event(
                logger,
                logging.DEBUG,
                "chat.model.chunk.summary",
                round=rounds,
                chunk_count=chunk_count,
                chunks_with_choices=chunks_with_choices,
                chunks_with_delta=chunks_with_delta,
                chunks_with_content=chunks_with_content,
                chunks_with_tool_calls=chunks_with_tool_calls,
                finish_reason=str(finish_reason or ""),
                first_chunk_summary=first_chunk_summary or {},
                last_chunk_summary=last_chunk_summary or {},
                **base_log_context,
            )
            if unknown_delta_keys:
                _log_event(
                    logger,
                    logging.INFO,
                    "chat.model.unknown_delta_fields",
                    round=rounds,
                    unknown_delta_keys=sorted(unknown_delta_keys),
                    **base_log_context,
                )
            if assistant_summary["has_thinking"]:
                _log_event(
                    logger,
                    logging.DEBUG,
                    "chat.assistant.thinking",
                    round=rounds,
                    thinking_chars=assistant_summary["thinking_chars"],
                    thinking_preview=assistant_summary["thinking_preview"],
                    **base_log_context,
                )
            _log_event(
                logger,
                logging.INFO,
                "chat.assistant.answer",
                round=rounds,
                finish_reason=str(finish_reason or ""),
                answer_chars=assistant_summary["answer_chars"],
                answer_preview=assistant_summary["answer_preview"],
                **base_log_context,
            )
            if chunk_count > 0 and assistant_summary["content_chars"] == 0 and not tool_calls:
                _log_event(
                    logger,
                    logging.WARNING,
                    "chat.model.empty_output",
                    round=rounds,
                    finish_reason=str(finish_reason or ""),
                    chunk_count=chunk_count,
                    chunks_with_choices=chunks_with_choices,
                    chunks_with_delta=chunks_with_delta,
                    first_chunk_preview=first_chunk_preview,
                    last_chunk_preview=last_chunk_preview,
                    first_chunk_summary=first_chunk_summary or {},
                    last_chunk_summary=last_chunk_summary or {},
                    **base_log_context,
                )
            answer_missing = assistant_summary["answer_chars"] == 0 and not tool_calls
            stream_incomplete = chunk_count > 0 and finish_reason is None and answer_missing
            empty_stopped_answer = chunk_count > 0 and finish_reason is not None and answer_missing and retry_on_empty_answer_stop
            if stream_incomplete or empty_stopped_answer:
                if empty_answer_retry_attempts < max_empty_answer_retries:
                    empty_answer_retry_attempts += 1
                    _log_event(
                        logger,
                        logging.WARNING,
                        ("chat.model.incomplete_stream.retry" if stream_incomplete else "chat.model.empty_answer_stop.retry"),
                        round=rounds,
                        retry_attempt=empty_answer_retry_attempts,
                        max_retry_count=max_empty_answer_retries,
                        finish_reason=str(finish_reason or ""),
                        chunk_count=chunk_count,
                        chunks_with_choices=chunks_with_choices,
                        chunks_with_delta=chunks_with_delta,
                        first_chunk_summary=first_chunk_summary or {},
                        last_chunk_summary=last_chunk_summary or {},
                        **base_log_context,
                    )
                    continue
                if stream_incomplete:
                    raise IncompleteStreamError(INCOMPLETE_STREAM_ERROR_MESSAGE)
            if tool_calls:
                _log_event(
                    logger,
                    logging.INFO,
                    "chat.assistant.tool_calls",
                    round=rounds,
                    tool_calls=[summarize_tool_call_for_log(tool_call) for tool_call in tool_calls],
                    **base_log_context,
                )

            if not tool_calls:
                return

            messages.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls})

            tool_results: list[tuple[dict[str, Any], str, str]] = []
            for tool_call in tool_calls:
                tool_started_at = time.perf_counter()
                _log_event(
                    logger,
                    logging.INFO,
                    "chat.tool.start",
                    round=rounds,
                    **summarize_tool_call_for_log(tool_call),
                    **base_log_context,
                )
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "tool_status": {
                                "phase": "start",
                                "tool_call_id": tool_call["id"],
                                "tool_name": tool_call["function"]["name"],
                            }
                        }
                    )
                    + "\n\n"
                )
                await asyncio.sleep(0)
                error_text = ""
                result_text = ""
                try:
                    result = await execute_tool_nonblocking(tool_call, tool_executor)
                    result_text = str(result)
                except ToolExecutionError as error:
                    error_text = str(error)
                tool_results.append((tool_call, result_text, error_text))
                _log_event(
                    logger,
                    logging.INFO if not error_text else logging.WARNING,
                    "chat.tool.finish" if not error_text else "chat.tool.error",
                    round=rounds,
                    duration_ms=round((time.perf_counter() - tool_started_at) * 1000, 2),
                    **summarize_tool_result_for_log(tool_call, result_text, error_text),
                    **base_log_context,
                )
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "tool_call": {
                                "tool_call_id": tool_call["id"],
                                "tool_name": tool_call["function"]["name"],
                                "arguments_json": tool_call["function"]["arguments"],
                                "content": result_text,
                                "error_text": error_text,
                            }
                        }
                    )
                    + "\n\n"
                )

            for tool_call, result_text, error_text in tool_results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": error_text or result_text,
                    }
                )

    except OpenAIError as error:
        _log_event(logger, logging.ERROR, "chat.stream.openai_error", error_message=str(error), **base_log_context)
        logger.exception("OpenAI error")
        yield f"data: {json.dumps({'error': map_openai_error_message(error)})}\n\n"
    except IncompleteStreamError as error:
        _log_event(
            logger,
            logging.ERROR,
            "chat.stream.incomplete_output",
            error_message=str(error),
            **base_log_context,
        )
        yield f"data: {json.dumps({'error': str(error)})}\n\n"
    except Exception as error:
        _log_event(
            logger,
            logging.ERROR,
            "chat.stream.error",
            error_type=error.__class__.__name__,
            error_message=str(error),
            **base_log_context,
        )
        logger.exception("Streaming error")
        error_message = "Streaming failed"
        if error.__class__.__name__ == "MCPClientError":
            error_message = str(error) or "MCP request failed"
        yield f"data: {json.dumps({'error': error_message})}\n\n"
    finally:
        _log_event(logger, logging.INFO, "chat.stream.closed", **base_log_context)
