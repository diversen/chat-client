from chat_client.core import exceptions_validation

from chat_client.models import Dialog, Message, Image, MessageImage, ToolCallEvent
from chat_client.database.db_session import async_session
import uuid
import logging
import json
from sqlalchemy import select, func, update, delete, exists, or_

logger: logging.Logger = logging.getLogger(__name__)

DIALOGS_PER_PAGE = 20


async def create_dialog(user_id: int, title: str):

    async with async_session() as session:
        dialog_id = str(uuid.uuid4())
        new_dialog = Dialog(
            dialog_id=dialog_id,
            user_id=user_id,
            title=title,
        )
        session.add(new_dialog)
        await session.commit()

        return dialog_id


async def create_message(
    user_id: int,
    dialog_id: str,
    role: str,
    content: str,
    images: list[dict[str, str]] | None = None,
):

    async with async_session() as session:
        new_message = Message(
            role=role,
            content=content,
            dialog_id=dialog_id,
            user_id=user_id,
        )
        session.add(new_message)
        await session.flush()
        message_id = new_message.message_id
        if message_id is None:
            raise RuntimeError("Failed to create message id")

        for image in images or []:
            data_url = str(image.get("data_url", "")).strip()
            if not data_url.startswith("data:image/"):
                continue

            new_image = Image(data_url=data_url)
            session.add(new_image)
            await session.flush()
            image_id = new_image.image_id
            if image_id is None:
                continue
            session.add(
                MessageImage(
                    message_id=message_id,
                    image_id=image_id,
                )
            )

        await session.commit()
        await session.refresh(new_message)

        return new_message.message_id


async def get_dialog(user_id: int, dialog_id: str):

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise exceptions_validation.UserValidate("Dialog not found or not owned by user")

        assert dialog.created is not None

        return {
            "dialog_id": str(dialog.dialog_id),
            "title": dialog.title,
            "created": dialog.created.isoformat(),
        }


async def get_messages(user_id: int, dialog_id: str):

    async with async_session() as session:
        stmt = (
            select(Message)
            .where(Message.dialog_id == dialog_id, Message.user_id == user_id, Message.active == 1)
            .order_by(Message.created.asc())
            .limit(1000)
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        message_ids = [m.message_id for m in messages if m.message_id is not None]
        images_by_message: dict[int, list[dict[str, str]]] = {}
        if message_ids:
            image_stmt = (
                select(MessageImage.message_id, Image.data_url)
                .join(Image, Image.image_id == MessageImage.image_id)
                .where(MessageImage.message_id.in_(message_ids))
                .order_by(MessageImage.message_image_id.asc())
            )
            image_result = await session.execute(image_stmt)
            for message_id, data_url in image_result.all():
                images_by_message.setdefault(message_id, []).append({"data_url": data_url})

        combined_rows: list[tuple] = []
        for m in messages:
            assert m.created is not None
            message_id = m.message_id
            if message_id is None:
                continue
            combined_rows.append(
                (
                    m.created,
                    {
                        "message_id": str(message_id),
                        "role": m.role,
                        "content": m.content,
                        "images": images_by_message.get(message_id, []),
                        "created": m.created.isoformat(),
                    },
                )
            )

        tool_stmt = (
            select(ToolCallEvent)
            .where(ToolCallEvent.dialog_id == dialog_id, ToolCallEvent.user_id == user_id)
            .order_by(ToolCallEvent.created.asc())
        )
        tool_result = await session.execute(tool_stmt)
        tool_events = tool_result.scalars().all()
        for event in tool_events:
            assert event.created is not None
            combined_rows.append(
                (
                    event.created,
                    {
                        "message_id": None,
                        "role": "tool",
                        "content": event.result_text if event.result_text else event.error_text,
                        "images": [],
                        "created": event.created.isoformat(),
                        "tool_call_id": event.tool_call_id,
                        "tool_name": event.tool_name,
                        "arguments_json": event.arguments_json,
                        "error_text": event.error_text,
                    },
                )
            )

        combined_rows.sort(key=lambda row: row[0])
        return [row[1] for row in combined_rows]


async def create_tool_call_event(
    user_id: int,
    dialog_id: str,
    tool_call_id: str,
    tool_name: str,
    arguments: dict,
    result_text: str = "",
    error_text: str = "",
):
    async with async_session() as session:
        event = ToolCallEvent(
            user_id=user_id,
            dialog_id=dialog_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments_json=json.dumps(arguments),
            result_text=result_text,
            error_text=error_text,
        )
        session.add(event)
        await session.commit()


async def delete_dialog(user_id: int, dialog_id: str):

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise exceptions_validation.UserValidate("Dialog is not connected to user. You can't delete it")

        await session.delete(dialog)
        await session.commit()


async def get_dialogs_info(user_id: int, current_page: int = 1, query: str = ""):

    async with async_session() as session:
        query = str(query).strip()

        filters = [Dialog.user_id == user_id]
        if query:
            pattern = f"%{query}%"
            message_match_exists = exists(
                select(1).where(
                    Message.dialog_id == Dialog.dialog_id,
                    Message.user_id == user_id,
                    Message.active == 1,
                    Message.content.ilike(pattern),
                )
            )
            filters.append(
                or_(
                    Dialog.title.ilike(pattern),
                    message_match_exists,
                )
            )

        # Fetch dialogs for the current page
        stmt = (
            select(Dialog)
            .where(*filters)
            .order_by(Dialog.created.desc(), Dialog.dialog_id.desc())
            .limit(DIALOGS_PER_PAGE)
            .offset((current_page - 1) * DIALOGS_PER_PAGE)
        )
        result = await session.execute(stmt)
        dialogs = result.scalars().all()

        # Count total number of dialogs
        count_stmt = select(func.count()).select_from(Dialog).where(*filters)
        count_result = await session.execute(count_stmt)
        num_dialogs = count_result.scalar_one()

        has_prev = current_page > 1
        has_next = num_dialogs > current_page * DIALOGS_PER_PAGE
        prev_page = current_page - 1 if has_prev else 0
        next_page = current_page + 1 if has_next else 0

        logger.warning(f"Dialogs for user {user_id}: {len(dialogs)} found on page {current_page} (query={query!r})")

        dialogs_list = []
        for d in dialogs:
            assert d.created is not None  # helps both Mypy and sanity
            dialogs_list.append(
                {
                    "dialog_id": str(d.dialog_id),
                    "title": d.title,
                    "created": d.created.isoformat(),
                }
            )

        return {
            "current_page": current_page,
            "per_page": DIALOGS_PER_PAGE,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_page": prev_page,
            "next_page": next_page,
            "dialogs": dialogs_list,
            "num_dialogs": num_dialogs,
        }


async def update_message(user_id: int, message_id: int, new_content: str):
    """
    Update a message and deactivate newer messages in the same dialog
    """
    new_content = str(new_content).strip()

    if not new_content:
        raise exceptions_validation.UserValidate("Message content cannot be empty")

    async with async_session() as session:
        # First, get the message to update and verify ownership
        stmt = select(Message).where(Message.message_id == message_id, Message.user_id == user_id)
        result = await session.execute(stmt)
        message = result.scalar_one_or_none()

        if not message:
            raise exceptions_validation.UserValidate("Message not found or not owned by user")

        # Update the message content
        message.content = new_content

        # Deactivate all messages in the same dialog that were created after this message
        deactivate_stmt = (
            update(Message)
            .where(Message.dialog_id == message.dialog_id, Message.created > message.created, Message.user_id == user_id)
            .values(active=0)
        )
        await session.execute(deactivate_stmt)

        # Remove tool call events that belong to turns after the edited message.
        delete_tool_events_stmt = delete(ToolCallEvent).where(
            ToolCallEvent.dialog_id == message.dialog_id,
            ToolCallEvent.user_id == user_id,
            ToolCallEvent.created > message.created,
        )
        await session.execute(delete_tool_events_stmt)

        await session.commit()

        return {"message_id": message_id, "content": new_content, "updated": True}
