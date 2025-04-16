import time
from typing import Any, Optional
from starlette.requests import Request
import logging
from chat_client.database.crud import CRUD
from chat_client.database.database_utils import DatabaseConnection
from config import DATABASE


logger: logging.Logger = logging.getLogger(__name__)


def set_session_variable(request: Request, key: str, value: Any, ttl: int = 0) -> None:
    """
    Set a session variable with optional TTL.
    If TTL is provided, the variable will expire after TTL seconds.
    """
    data = {"value": value}
    if ttl:
        data["expires_at"] = time.time() + ttl
    request.session[key] = data


def get_session_variable(request: Request, key: str) -> Optional[Any]:
    """
    Get a session variable, returning None if it does not exist or is expired.
    """
    data = request.session.get(key)

    # Data needs to be a dict
    if not isinstance(data, dict):
        return None

    if data is None:
        return None

    # If the variable has an expiry and it's expired, remove it and return None
    expires_at = data.get("expires_at")
    if expires_at and time.time() > expires_at:
        del request.session[key]
        return None

    return data["value"]


def delete_session_variable(request: Request, key: str) -> None:
    """
    Delete a session variable.
    """
    if key in request.session:
        del request.session[key]


def set_user_session(request: Request, user_id: int, session_token, ttl=0) -> None:
    """
    Log in a user.
    """
    set_session_variable(request, "user_id", user_id, ttl)
    set_session_variable(request, "token", session_token, ttl)


async def is_logged_in(request: Request) -> int:
    """
    Check if a user is logged in. Return the user_id if they are. Else return 0.
    """
    user_id = get_session_variable(request, "user_id")
    token = get_session_variable(request, "token")

    if not user_id or not token:
        return 0

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)
        token_valid = await crud.exists(
            "user_token",
            filters={
                "user_id": user_id,
                "token": token,
            },
        )
        if not token_valid:
            return 0

    if user_id:
        return user_id

    return 0


async def clear_user_session(request: Request, all: bool = False) -> None:
    """
    Log out a user.
    """
    user_id = get_session_variable(request, "user_id")
    token = get_session_variable(request, "token")

    delete_session_variable(request, "user_id")
    delete_session_variable(request, "token")

    # remove token
    if token and user_id:
        if all:
            filters = {
                "user_id": user_id,
            }
        else:
            filters = {
                "user_id": user_id,
                "token": token,
            }

        database_connection = DatabaseConnection(DATABASE)
        async with database_connection.async_transaction_scope() as connection:
            crud = CRUD(connection)
            await crud.delete(
                "user_token",
                filters=filters,
            )
