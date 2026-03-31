import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from inspect import isawaitable, iscoroutinefunction
from typing import Any

from openai import OpenAIError
from starlette.requests import Request


GENERIC_OPENAI_ERROR_MESSAGE = "An error occurred. Please try again later."
IMAGE_MODALITY_ERROR_MESSAGE = "The selected model does not support image inputs. Remove attached images or choose a vision model."
TOOL_ROUTER_MAX_TOKENS = 64
MAX_TOOL_LOOP_ROUNDS = 8


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

        content = str(message.get("content", ""))
        images = message.get("images", [])
        if not isinstance(images, list) or not images:
            normalized.append(message)
            continue

        content_parts: list[dict[str, Any]] = []
        if content:
            content_parts.append({"type": "text", "text": content})

        for image in images:
            if not isinstance(image, dict):
                continue
            data_url = str(image.get("data_url", "")).strip()
            if not data_url.startswith("data:image/"):
                continue
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                }
            )

        if content_parts:
            normalized.append({"role": "user", "content": content_parts})
        else:
            normalized.append({"role": "user", "content": content})

    return normalized


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


def execute_tool(tool_call: dict[str, Any], tool_registry: dict[str, Callable[..., Any]], logger: logging.Logger) -> Any:
    """
    Execute a model tool call from the configured registry.
    """
    func_name = str(tool_call.get("function", {}).get("name", "")).strip()
    args = parse_tool_arguments(tool_call, logger)
    logger.info(f"Executing tool: {func_name}({args})")

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
            raise ToolArgumentsError(
                f'Tool "{tool_name}" requires argument "{arg_name}" of type {expected_type}.'
            )


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
            if (
                previous_key
                and previous_key.startswith("tmp:")
                and previous_key in tool_calls_by_key
                and key not in tool_calls_by_key
            ):
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
    *,
    openai_client_cls: Callable[..., Any],
    provider_info_resolver: Callable[[str], dict[str, Any]],
    tool_models: list[str],
    tools_loader: Callable[[], list[dict[str, Any]]],
    tool_executor: Callable[[dict[str, Any]], Any],
    logger: logging.Logger,
) -> AsyncIterator[str]:
    try:
        provider_info = provider_info_resolver(model)

        client = openai_client_cls(
            api_key=provider_info.get("api_key"),
            base_url=provider_info.get("base_url"),
        )

        tools_enabled = model in tool_models
        tool_definitions = tools_loader() if tools_enabled else []

        rounds = 0
        while True:
            rounds += 1
            if rounds > MAX_TOOL_LOOP_ROUNDS:
                yield f"data: {json.dumps({'error': 'Tool loop exceeded maximum rounds'})}\n\n"
                return

            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
            }
            if tools_enabled:
                create_kwargs["tools"] = tool_definitions

            stream_response = client.chat.completions.create(**create_kwargs)
            disconnected = False
            assistant_content_parts: list[str] = []
            finish_reason: Any = None
            tool_call_state: dict[str, Any] = {
                "tool_calls_by_key": {},
                "tool_call_order": [],
                "index_active_key": {},
                "tmp_counter": 0,
            }

            try:
                for chunk in stream_response:
                    if await request.is_disconnected():
                        disconnected = True
                        break

                    model_dict = chunk.model_dump()
                    json_chunk = json.dumps(model_dict)
                    yield f"data: {json_chunk}\n\n"

                    choices = getattr(chunk, "choices", None)
                    if not isinstance(choices, list) or not choices:
                        continue
                    first_choice = choices[0]
                    delta = getattr(first_choice, "delta", None)
                    if delta is not None:
                        content_piece = getattr(delta, "content", None)
                        if isinstance(content_piece, str) and content_piece:
                            assistant_content_parts.append(content_piece)
                        _append_stream_tool_call_deltas(getattr(delta, "tool_calls", None), tool_call_state)
                    if getattr(first_choice, "finish_reason", None) is not None:
                        finish_reason = getattr(first_choice, "finish_reason", None)
            finally:
                _close_stream(stream_response, logger)

            if disconnected:
                return

            tool_calls = _collect_streamed_tool_calls(tool_call_state)
            assistant_content = "".join(assistant_content_parts)
            logger.info(
                "Streamed assistant message: %s",
                {
                    "finish_reason": str(finish_reason or ""),
                    "content": assistant_content,
                    "tool_calls": tool_calls,
                },
            )

            if not tool_calls:
                return

            messages.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls})

            tool_results: list[tuple[dict[str, Any], str, str]] = []
            for tool_call in tool_calls:
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
        logger.exception("OpenAI error")
        yield f"data: {json.dumps({'error': map_openai_error_message(error)})}\n\n"
    except Exception as error:
        logger.exception("Streaming error")
        error_message = "Streaming failed"
        if error.__class__.__name__ == "MCPClientError":
            error_message = str(error) or "MCP request failed"
        yield f"data: {json.dumps({'error': error_message})}\n\n"
    finally:
        logger.info("Closing stream")
