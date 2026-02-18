import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from openai import OpenAIError
from starlette.requests import Request


GENERIC_OPENAI_ERROR_MESSAGE = "An error occurred. Please try again later."
IMAGE_MODALITY_ERROR_MESSAGE = "The selected model does not support image inputs. Remove attached images or choose a vision model."


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


async def chat_response_stream(
    request: Request,
    messages: list[dict[str, Any]],
    model: str,
    logged_in: int,
    *,
    get_profile: Callable[[int], Any],
    openai_client_cls: Callable[..., Any],
    provider_info_resolver: Callable[[str], dict[str, Any]],
    tool_models: list[str],
    tools_loader: Callable[[], list[dict[str, Any]]],
    tool_executor: Callable[[dict[str, Any]], Any],
    logger: logging.Logger,
) -> AsyncIterator[str]:
    profile = await get_profile(logged_in)
    if "system_message" in profile and profile["system_message"]:
        system_message = profile["system_message"]
        logger.debug(f"System message: {system_message}")
        messages.insert(0, {"role": "user", "content": system_message})

    try:
        provider_info = provider_info_resolver(model)

        client = openai_client_cls(
            api_key=provider_info.get("api_key"),
            base_url=provider_info.get("base_url"),
        )

        chat_args: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        if model in tool_models:
            chat_args["tools"] = tools_loader()

        stream_response = client.chat.completions.create(**chat_args)
        tool_call: dict[str, Any] = {}
        disconnected = False
        try:
            for chunk in stream_response:
                if await request.is_disconnected():
                    disconnected = True
                    break

                delta = chunk.choices[0].delta

                if delta.tool_calls:
                    call = delta.tool_calls[0]
                    if not tool_call:
                        tool_call = {
                            "id": call.id,
                            "type": call.type,
                            "function": {"name": "", "arguments": ""},
                        }

                    if call.function and call.function.name:
                        tool_call["function"]["name"] += call.function.name
                    if call.function and call.function.arguments:
                        tool_call["function"]["arguments"] += call.function.arguments

                if chunk.choices[0].finish_reason == "tool_calls":
                    break

                model_dict = chunk.model_dump()
                json_chunk = json.dumps(model_dict)
                yield f"data: {json_chunk}\n\n"
        finally:
            _close_stream(stream_response, logger)

        if disconnected:
            return

        if tool_call:
            result = tool_executor(tool_call)

            messages.append({"role": "assistant", "tool_calls": [tool_call]})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                }
            )

            tool_response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )

            try:
                for chunk in tool_response:
                    if await request.is_disconnected():
                        break

                    model_dict = chunk.model_dump()
                    json_chunk = json.dumps(model_dict)
                    yield f"data: {json_chunk}\n\n"
            finally:
                _close_stream(tool_response, logger)

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
