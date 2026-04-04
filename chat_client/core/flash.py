"""
Set and get flash messages to be displayed to the user.
"""

import typing
from starlette.requests import Request


def _get_flash_store(request: Request) -> list[dict[str, str]]:
    flash_store = request.scope.setdefault("flash_session", {})
    messages = flash_store.get("flash")
    if not isinstance(messages, list):
        messages = []
        flash_store["flash"] = messages
    return messages


def _set_message(request: Request, message: str, type="notice") -> None:
    """Set a flash message to be displayed to the user.
    Args:
        request: The request object.
        message: The message to display.
        type: The type of message. One of "notice", "success", "warning", "error".
    """
    if type not in ["notice", "success", "warning", "error"]:
        type = "notice"

    _get_flash_store(request).append({"type": type, "message": message})


def set_notice(request: Request, message: str) -> None:
    """Set a notice message to be displayed to the user."""
    _set_message(request, message, "notice")


def set_success(request: Request, message: str) -> None:
    """Set a success message to be displayed to the user."""
    _set_message(request, message, "success")


def set_warning(request: Request, message: str) -> None:
    _set_message(request, message, "warning")


def set_error(request: Request, message: str) -> None:
    _set_message(request, message, "error")


def get_messages(request) -> typing.List:
    """Get a flash message to be displayed to the user."""
    flash_store = request.scope.setdefault("flash_session", {})
    messages = flash_store.pop("flash", [])
    if isinstance(messages, list):
        return messages
    return []
