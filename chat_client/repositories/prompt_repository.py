"""Data-access helpers for Prompt CRUD operations."""

from sqlalchemy import select, update, delete
from starlette.requests import Request

from chat_client.database.db_session import async_session
from chat_client.core import exceptions_validation
from chat_client.models import Prompt
from chat_client.core import user_session

MAX_TITLE_LEN = 256
MAX_PROMPT_LEN = 8096


async def _validate(title: str, prompt_text: str):
    if not title:
        raise exceptions_validation.UserValidate("Title is required")
    if len(title) > MAX_TITLE_LEN:
        raise exceptions_validation.UserValidate(f"Title must be ≤ {MAX_TITLE_LEN} characters")
    if not prompt_text:
        raise exceptions_validation.UserValidate("Prompt is required")
    if len(prompt_text) > MAX_PROMPT_LEN:
        raise exceptions_validation.UserValidate(f"Prompt must be ≤ {MAX_PROMPT_LEN} characters")


async def create_prompt(user_id: int, request: Request):

    form = await request.json()
    title = str(form.get("title", ""))
    prompt_text = str(form.get("prompt", ""))

    await _validate(title, prompt_text)

    async with async_session() as session:
        new_prompt = Prompt(title=title, prompt=prompt_text, user_id=user_id)
        session.add(new_prompt)
        await session.commit()
        return {"prompt_id": new_prompt.prompt_id}


async def list_prompts(user_id: int):
    async with async_session() as session:
        stmt = select(Prompt).where(Prompt.user_id == user_id).order_by(Prompt.prompt_id.desc())
        res = await session.execute(stmt)
        return res.scalars().all()


async def get_prompt(user_id: int, prompt_id: int):
    async with async_session() as session:
        stmt = select(Prompt).where(Prompt.user_id == user_id, Prompt.prompt_id == prompt_id)
        res = await session.execute(stmt)
        prompt = res.scalar_one_or_none()
        return prompt


async def update_prompt(request: Request, prompt_id: int):
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        raise exceptions_validation.UserValidate("You must be logged in to update prompts")

    form = await request.json()
    title = str(form.get("title", ""))
    prompt_text = str(form.get("prompt", ""))

    await _validate(title, prompt_text)

    async with async_session() as session:
        stmt = (
            update(Prompt)
            .where(Prompt.user_id == user_id, Prompt.prompt_id == prompt_id)
            .values(title=title, prompt=prompt_text)
            .execution_options(synchronize_session="fetch")
        )
        result = await session.execute(stmt)
        if result.rowcount == 0:
            raise exceptions_validation.UserValidate("Prompt not found or no permission")
        await session.commit()


async def delete_prompt(request: Request, prompt_id: int):
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        raise exceptions_validation.UserValidate("You must be logged in to delete prompts")

    async with async_session() as session:
        stmt = delete(Prompt).where(Prompt.user_id == user_id, Prompt.prompt_id == prompt_id)
        result = await session.execute(stmt)
        if result.rowcount == 0:
            raise exceptions_validation.UserValidate("Prompt not found or no permission")
        await session.commit()
