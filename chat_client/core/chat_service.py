import json
import logging
from collections.abc import AsyncIterator, Callable
from inspect import isawaitable
from typing import Any

from openai import OpenAIError
from starlette.requests import Request


GENERIC_OPENAI_ERROR_MESSAGE = "An error occurred. Please try again later."
IMAGE_MODALITY_ERROR_MESSAGE = "The selected model does not support image inputs. Remove attached images or choose a vision model."
TOOL_ROUTER_MAX_TOKENS = 64


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
    func_name = tool_call["function"]["name"]
    args = parse_tool_arguments(tool_call, logger)
    logger.info(f"Executing tool: {func_name}({args})")

    if func_name in tool_registry:
        return tool_registry[func_name](**args)

    return f"Unknown tool: {func_name}"


def parse_tool_arguments(tool_call: dict[str, Any], logger: logging.Logger) -> dict[str, Any]:
    raw_args = tool_call.get("function", {}).get("arguments", "{}")
    try:
        parsed = json.loads(raw_args)
    except json.JSONDecodeError:
        logger.exception("Invalid tool call arguments JSON")
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


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
        if not tools_enabled:
            stream_response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            disconnected = False
            try:
                for chunk in stream_response:
                    if await request.is_disconnected():
                        disconnected = True
                        break

                    model_dict = chunk.model_dump()
                    json_chunk = json.dumps(model_dict)
                    yield f"data: {json_chunk}\n\n"
            finally:
                _close_stream(stream_response, logger)

            if disconnected:
                return
            return

        tool_decision_response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools_loader(),
            max_tokens=TOOL_ROUTER_MAX_TOKENS,
            stream=False,
        )
        choices = getattr(tool_decision_response, "choices", None)
        if not isinstance(choices, list) or not choices:
            return

        first_choice = choices[0]
        assistant_message = getattr(first_choice, "message", None)
        logger.info(
            "First non-streaming assistant message: %s",
            _summarize_assistant_message_for_log(assistant_message, getattr(first_choice, "finish_reason", None)),
        )
        tool_calls = _normalize_tool_calls(getattr(assistant_message, "tool_calls", None))

        if tool_calls:
            tool_results: list[tuple[dict[str, Any], Any]] = []
            for tool_call in tool_calls:
                result = tool_executor(tool_call)
                if isawaitable(result):
                    result = await result
                tool_results.append((tool_call, result))
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "tool_call": {
                                "tool_call_id": tool_call["id"],
                                "tool_name": tool_call["function"]["name"],
                                "arguments_json": tool_call["function"]["arguments"],
                                "content": str(result),
                                "error_text": "",
                            }
                        }
                    )
                    + "\n\n"
                )

            messages.append({"role": "assistant", "tool_calls": tool_calls})
            for tool_call, result in tool_results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result,
                    }
                )

            final_response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            try:
                for chunk in final_response:
                    if await request.is_disconnected():
                        return
                    model_dict = chunk.model_dump()
                    json_chunk = json.dumps(model_dict)
                    yield f"data: {json_chunk}\n\n"
            finally:
                _close_stream(final_response, logger)
            return

        final_response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        try:
            for chunk in final_response:
                if await request.is_disconnected():
                    return
                model_dict = chunk.model_dump()
                json_chunk = json.dumps(model_dict)
                yield f"data: {json_chunk}\n\n"
        finally:
            _close_stream(final_response, logger)
        return

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
