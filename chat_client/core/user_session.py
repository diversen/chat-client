import time
from typing import Any, Optional
from starlette.requests import Request
import logging
from chat_client._models import UserToken

# from data.config import SESSION_EXPIRE_TIME_IN_SECONDS  # optional future config
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from chat_client.database.db_session import async_session

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

    if not isinstance(data, dict):
        return None

    expires_at = data.get("expires_at")
    if expires_at and time.time() > expires_at:
        del request.session[key]
        return None

    return data.get("value")


def delete_session_variable(request: Request, key: str) -> None:
    """
    Delete a session variable.
    """
    if key in request.session:
        del request.session[key]


def set_user_session(request: Request, user_id: int, session_token: str, ttl: int = 0) -> None:
    """
    Log in a user.
    """
    set_session_variable(request, "user_id", user_id, ttl)
    set_session_variable(request, "token", session_token, ttl)


async def is_logged_in_with_session(request: Request, session: AsyncSession) -> int:
    user_id = get_session_variable(request, "user_id")
    token = get_session_variable(request, "token")

    if not user_id or not token:
        return 0

    stmt = select(UserToken).where(UserToken.user_id == user_id, UserToken.token == token)
    result = await session.execute(stmt)
    user_token = result.scalar_one_or_none()

    if not user_token:
        return 0

    if user_token.expires and user_token.expires < int(time.time()):
        return 0

    return user_id


async def is_logged_in(request: Request) -> int:
    async with async_session() as session:
        return await is_logged_in_with_session(request, session)


async def clear_user_session(request: Request, all: bool = False) -> None:
    """
    Log out a user.
    """
    user_id = get_session_variable(request, "user_id")
    token = get_session_variable(request, "token")

    delete_session_variable(request, "user_id")
    delete_session_variable(request, "token")

    if token and user_id:
        async with async_session() as session:
            if all:
                stmt = delete(UserToken).where(UserToken.user_id == user_id)
            else:
                stmt = delete(UserToken).where(UserToken.user_id == user_id, UserToken.token == token)

            await session.execute(stmt)
            await session.commit()
