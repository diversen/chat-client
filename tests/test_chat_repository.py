import asyncio
import tempfile
from pathlib import Path
from types import ModuleType
import sys

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chat_client.models import AssistantTurnEvent, Base, Dialog, ToolCallEvent, User


def _aiosqlite_available() -> bool:
    async def _probe() -> None:
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "probe.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql("SELECT 1")
        finally:
            await engine.dispose()
            if db_path.exists():
                db_path.unlink()
            Path(temp_dir).rmdir()

    try:
        asyncio.run(asyncio.wait_for(_probe(), timeout=1.0))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _aiosqlite_available(),
    reason="aiosqlite connections hang in this environment",
)


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


def test_get_messages_returns_assistant_turn_items():
    async def _run():
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_chat_repository_assistant_turn.db"
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
                    email="repo-test-assistant-turn@example.com",
                    password_hash="x",
                    random="y",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = int(user.user_id)

            dialog_id = await chat_repository.create_dialog(user_id, "Assistant turn history")
            await chat_repository.create_message(user_id, dialog_id, "user", "Hello")
            await chat_repository.create_assistant_turn_events(
                user_id=user_id,
                dialog_id=dialog_id,
                turn_id="turn-1",
                events=[
                    {"event_type": "assistant_segment", "reasoning_text": "thoughts", "content_text": ""},
                    {
                        "event_type": "tool_call",
                        "tool_call_id": "call_x",
                        "tool_name": "ping",
                        "arguments_json": "{}",
                        "result_text": "pong",
                    },
                    {"event_type": "assistant_segment", "reasoning_text": "", "content_text": "Useful answer"},
                ],
            )

            messages = await chat_repository.get_messages(user_id, dialog_id)

            assert messages[0]["role"] == "user"
            assert messages[1]["role"] == "assistant_turn"
            assert len(messages[1]["events"]) == 3
            assert messages[1]["events"][0]["event_type"] == "assistant_segment"
            assert messages[1]["events"][1]["event_type"] == "tool_call"
            assert messages[1]["events"][2]["content_text"] == "Useful answer"

        finally:
            chat_repository.async_session = original_session_factory
            sys.modules.pop("data.config", None)
            sys.modules.pop("data", None)
            await engine.dispose()
            if db_path.exists():
                db_path.unlink()
            Path(temp_dir).rmdir()

    asyncio.run(_run())


def test_update_dialog_title_updates_existing_dialog():
    async def _run():
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_chat_repository_update_dialog_title.db"
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
                    email="repo-test-update-title@example.com",
                    password_hash="x",
                    random="y",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = int(user.user_id)

            dialog_id = await chat_repository.create_dialog(user_id, "New chat")
            result = await chat_repository.update_dialog_title(user_id, dialog_id, "Short summary")

            assert result["dialog_id"] == dialog_id
            assert result["title"] == "Short summary"

            async with session_factory() as session:
                title = (
                    (
                        await session.execute(
                            select(Dialog.title).where(Dialog.dialog_id == dialog_id)
                        )
                    )
                    .scalar_one()
                )

            assert title == "Short summary"
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
                    email="repo-test-sequence@example.com",
                    password_hash="x",
                    random="y",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = int(user.user_id)

            dialog_id = await chat_repository.create_dialog(user_id, "Same timestamp order")
            user_msg_id = await chat_repository.create_message(user_id, dialog_id, "user", "Question")
            await chat_repository.create_assistant_turn_events(
                user_id=user_id,
                dialog_id=dialog_id,
                turn_id="turn-seq",
                events=[
                    {
                        "event_type": "tool_call",
                        "tool_call_id": "call_same",
                        "tool_name": "python_hardened",
                        "arguments_json": '{"code":"1+1"}',
                        "result_text": "2",
                    },
                    {"event_type": "assistant_segment", "content_text": "Final answer"},
                ],
            )

            # Force equal timestamps and scrambled sequence indexes; ordering must follow sequence_index.
            async with session_factory() as session:
                same_ts = "2026-01-01 00:00:00"
                await session.execute(
                    text("UPDATE message SET created = :ts WHERE message_id = :uid"),
                    {"ts": same_ts, "uid": int(user_msg_id)},
                )
                await session.execute(
                    text("UPDATE assistant_turn_event SET created = :ts WHERE turn_id = 'turn-seq'"),
                    {"ts": same_ts},
                )
                await session.execute(
                    text("UPDATE message SET sequence_index = 20 WHERE message_id = :uid"),
                    {"uid": int(user_msg_id)},
                )
                await session.execute(
                    text("UPDATE assistant_turn_event SET sequence_index = 10 WHERE turn_id = 'turn-seq'"),
                )
                await session.commit()

            messages = await chat_repository.get_messages(user_id, dialog_id)
            roles = [msg["role"] for msg in messages]
            assert roles == ["assistant_turn", "user"]
        finally:
            chat_repository.async_session = original_session_factory
            sys.modules.pop("data.config", None)
            sys.modules.pop("data", None)
            await engine.dispose()
            if db_path.exists():
                db_path.unlink()
            Path(temp_dir).rmdir()

    asyncio.run(_run())
