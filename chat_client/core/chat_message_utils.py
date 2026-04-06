import json
import re
from html import unescape
from typing import Any

from chat_client.core import chat_service

TITLE_FALLBACK_MAX_LENGTH = 80
PENDING_DIALOG_TITLES = {"New Chat"}
TITLE_FALLBACK_WORD_LIMIT = 25


def normalize_chat_messages(messages: list) -> list:
    return chat_service.normalize_chat_messages(messages)


def build_model_messages_from_dialog_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def strip_images_from_messages(messages: list[dict]) -> list[dict]:
    stripped: list[dict] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_copy = dict(message)
        message_copy["images"] = []
        stripped.append(message_copy)
    return stripped


def normalize_generated_dialog_title(value: str) -> str:
    normalized = str(value or "").strip()
    normalized = normalized.strip(" \t\r\n\"'`")
    normalized = " ".join(normalized.split())
    if len(normalized) > TITLE_FALLBACK_MAX_LENGTH:
        normalized = normalized[:TITLE_FALLBACK_MAX_LENGTH].rstrip(" ,.;:-")
    return normalized or "New Chat"


def derive_dialog_title_from_user_message(user_content: str) -> str:
    normalized = unescape(str(user_content or "").strip())
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"_+", " ", normalized)
    words = [word for word in normalized.split() if any(char.isalnum() for char in word)]
    if TITLE_FALLBACK_WORD_LIMIT > 0:
        words = words[:TITLE_FALLBACK_WORD_LIMIT]
    fallback_title = " ".join(words)
    if fallback_title:
        fallback_title = fallback_title[0].upper() + fallback_title[1:]
    return normalize_generated_dialog_title(fallback_title)


def is_pending_dialog_title(title: str) -> bool:
    normalized_title = str(title or "").strip()
    return normalized_title in PENDING_DIALOG_TITLES


def extract_first_user_message(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).strip()
        if role == "user":
            return str(message.get("content", "")).strip()
    return ""


def build_dialog_title_prompt(user_content: str) -> list[dict[str, str]]:
    normalized_user_content = str(user_content or "").strip()
    return [
        {
            "role": "system",
            "content": (
                "Generate a short title for a chat based on the first user message. "
                "Return only the title as plain text. Keep it short, typically under 10 words. "
                "Write it as a very short summary of the main topic or task. "
                "Do not use quotes. Do not add labels or explanations. "
                "Do not use HTML, XML, Markdown, code formatting, or any markup. "
                "Do not use math symbols or equations."
            ),
        },
        {
            "role": "user",
            "content": f"First user message:\n{normalized_user_content}",
        },
    ]
