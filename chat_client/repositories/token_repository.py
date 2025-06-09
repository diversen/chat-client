from chat_client._models import Token
import secrets
import arrow
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

EXPIRE_TIME_IN_MINUTES = 10

async def create_token(session: AsyncSession, type: str) -> str:
    token_value = secrets.token_urlsafe(32)

    token = Token(
        token=token_value,
        type=type,
        created=arrow.utcnow().datetime,
    )
    session.add(token)
    await session.commit()
    return token_value

async def validate_token(session: AsyncSession, token_value: str, type: str) -> bool:
    stmt = (
        select(Token)
        .where(Token.token == token_value, Token.type == type)
    )
    result = await session.execute(stmt)
    token_row = result.scalars().first()

    if not token_row:
        return False

    created_dt = arrow.get(token_row.created).datetime

    if arrow.utcnow().shift(minutes=-EXPIRE_TIME_IN_MINUTES).datetime > created_dt:
        return False

    return True
