import asyncio
import tempfile
from pathlib import Path
from types import ModuleType
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chat_client.models import Base, ToolCallEvent, User


def test_update_message_deletes_newer_tool_call_events():
    async def _run():
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_chat_repository.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        data_module = ModuleType("data")
        config_module = ModuleType("data.config")
        config_module.DATABASE = db_path
        data_module.config = config_module
        sys.modules["data"] = data_module
        sys.modules["data.config"] = config_module

        from chat_client.repositories import chat_repository

        original_session_factory = chat_repository.async_session
        chat_repository.async_session = session_factory
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with session_factory() as session:
                user = User(
                    email="repo-test@example.com",
                    password_hash="x",
                    random="y",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = int(user.user_id)

            dialog_id = await chat_repository.create_dialog(user_id, "Tool cleanup")
            message_id = await chat_repository.create_message(user_id, dialog_id, "user", "Original")

            await chat_repository.create_tool_call_event(
                user_id=user_id,
                dialog_id=dialog_id,
                tool_call_id="call_old",
                tool_name="old_tool",
                arguments={"x": 1},
                result_text="old",
            )
            await chat_repository.create_tool_call_event(
                user_id=user_id,
                dialog_id=dialog_id,
                tool_call_id="call_new",
                tool_name="new_tool",
                arguments={"x": 2},
                result_text="new",
            )

            async with session_factory() as session:
                await session.execute(
                    text("UPDATE message SET created = '2020-01-01 00:00:00' WHERE message_id = :message_id"),
                    {"message_id": message_id},
                )
                await session.execute(text("UPDATE tool_call_event SET created = '2019-01-01 00:00:00' WHERE tool_call_id = 'call_old'"))
                await session.execute(text("UPDATE tool_call_event SET created = '2021-01-01 00:00:00' WHERE tool_call_id = 'call_new'"))
                await session.commit()

            await chat_repository.update_message(user_id, int(message_id), "Edited")

            async with session_factory() as session:
                rows = (
                    (
                        await session.execute(
                            select(ToolCallEvent.tool_call_id)
                            .where(ToolCallEvent.dialog_id == dialog_id)
                            .order_by(ToolCallEvent.tool_call_id.asc())
                        )
                    )
                    .scalars()
                    .all()
                )

            assert rows == ["call_old"]
        finally:
            chat_repository.async_session = original_session_factory
            sys.modules.pop("data.config", None)
            sys.modules.pop("data", None)
            await engine.dispose()
            if db_path.exists():
                db_path.unlink()
            Path(temp_dir).rmdir()

    asyncio.run(_run())
