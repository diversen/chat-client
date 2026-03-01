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
                    text("UPDATE message SET sequence_index = 2 WHERE message_id = :message_id"),
                    {"message_id": message_id},
                )
                await session.execute(text("UPDATE tool_call_event SET sequence_index = 1 WHERE tool_call_id = 'call_old'"))
                await session.execute(text("UPDATE tool_call_event SET sequence_index = 3 WHERE tool_call_id = 'call_new'"))
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


def test_get_messages_filters_empty_assistant_messages():
    async def _run():
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_chat_repository_empty_assistant.db"
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
                    email="repo-test-empty-assistant@example.com",
                    password_hash="x",
                    random="y",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = int(user.user_id)

            dialog_id = await chat_repository.create_dialog(user_id, "Filter empty assistant")
            await chat_repository.create_message(user_id, dialog_id, "user", "Hello")
            await chat_repository.create_message(user_id, dialog_id, "assistant", "   ")
            await chat_repository.create_message(user_id, dialog_id, "assistant", "Useful answer")
            await chat_repository.create_tool_call_event(
                user_id=user_id,
                dialog_id=dialog_id,
                tool_call_id="call_x",
                tool_name="ping",
                arguments={},
                result_text="pong",
            )

            messages = await chat_repository.get_messages(user_id, dialog_id)

            assistant_contents = [m["content"] for m in messages if m.get("role") == "assistant"]
            tool_count = len([m for m in messages if m.get("role") == "tool"])

            assert assistant_contents == ["Useful answer"]
            assert tool_count == 1
        finally:
            chat_repository.async_session = original_session_factory
            sys.modules.pop("data.config", None)
            sys.modules.pop("data", None)
            await engine.dispose()
            if db_path.exists():
                db_path.unlink()
            Path(temp_dir).rmdir()

    asyncio.run(_run())


def test_get_messages_orders_by_sequence_index():
    async def _run():
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_chat_repository_same_timestamp_order.db"
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
                    email="repo-test-same-timestamp@example.com",
                    password_hash="x",
                    random="y",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = int(user.user_id)

            dialog_id = await chat_repository.create_dialog(user_id, "Same timestamp order")
            user_msg_id = await chat_repository.create_message(user_id, dialog_id, "user", "Question")
            await chat_repository.create_tool_call_event(
                user_id=user_id,
                dialog_id=dialog_id,
                tool_call_id="call_same",
                tool_name="python",
                arguments={"code": "1+1"},
                result_text="2",
            )
            assistant_msg_id = await chat_repository.create_message(user_id, dialog_id, "assistant", "Final answer")

            # Force equal timestamps and scrambled sequence indexes; ordering must follow sequence_index.
            async with session_factory() as session:
                same_ts = "2026-01-01 00:00:00"
                await session.execute(
                    text("UPDATE message SET created = :ts WHERE message_id IN (:uid, :aid)"),
                    {"ts": same_ts, "uid": int(user_msg_id), "aid": int(assistant_msg_id)},
                )
                await session.execute(
                    text("UPDATE tool_call_event SET created = :ts WHERE tool_call_id = 'call_same'"),
                    {"ts": same_ts},
                )
                await session.execute(
                    text("UPDATE message SET sequence_index = 20 WHERE message_id = :uid"),
                    {"uid": int(user_msg_id)},
                )
                await session.execute(
                    text("UPDATE tool_call_event SET sequence_index = 10 WHERE tool_call_id = 'call_same'"),
                )
                await session.execute(
                    text("UPDATE message SET sequence_index = 30 WHERE message_id = :aid"),
                    {"aid": int(assistant_msg_id)},
                )
                await session.commit()

            messages = await chat_repository.get_messages(user_id, dialog_id)
            roles = [msg["role"] for msg in messages]
            assert roles == ["user", "tool", "assistant"]
        finally:
            chat_repository.async_session = original_session_factory
            sys.modules.pop("data.config", None)
            sys.modules.pop("data", None)
            await engine.dispose()
            if db_path.exists():
                db_path.unlink()
            Path(temp_dir).rmdir()

    asyncio.run(_run())
