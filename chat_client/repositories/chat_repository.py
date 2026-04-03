from chat_client.core import exceptions_validation
from chat_client.repositories import attachment_repository
from chat_client.repositories import image_repository

from chat_client.models import Dialog, Message, Image, MessageImage, Attachment, MessageAttachment, ToolCallEvent, AssistantTurnEvent
from chat_client.database.db_session import async_session
import uuid
import logging
import json
from sqlalchemy import select, func, update, delete, exists, or_

logger: logging.Logger = logging.getLogger(__name__)

DIALOGS_PER_PAGE = 20


async def _next_dialog_sequence_index(session, user_id: int, dialog_id: str) -> int:
    return await _next_dialog_sequence_index_in_session(session, user_id, dialog_id)


async def _next_dialog_sequence_index_in_session(session, user_id: int, dialog_id: str) -> int:
    message_max_stmt = select(func.max(Message.sequence_index)).where(
        Message.dialog_id == dialog_id,
        Message.user_id == user_id,
    )
    tool_max_stmt = select(func.max(ToolCallEvent.sequence_index)).where(
        ToolCallEvent.dialog_id == dialog_id,
        ToolCallEvent.user_id == user_id,
    )
    assistant_turn_max_stmt = select(func.max(AssistantTurnEvent.sequence_index)).where(
        AssistantTurnEvent.dialog_id == dialog_id,
        AssistantTurnEvent.user_id == user_id,
    )
    message_max_result = await session.execute(message_max_stmt)
    tool_max_result = await session.execute(tool_max_stmt)
    assistant_turn_max_result = await session.execute(assistant_turn_max_stmt)
    message_max = message_max_result.scalar_one_or_none()
    tool_max = tool_max_result.scalar_one_or_none()
    assistant_turn_max = assistant_turn_max_result.scalar_one_or_none()
    max_sequence = max(int(message_max or 0), int(tool_max or 0), int(assistant_turn_max or 0))
    return max_sequence + 1


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


async def update_dialog_title(user_id: int, dialog_id: str, title: str):

    normalized_title = str(title).strip()
    if not normalized_title:
        raise exceptions_validation.UserValidate("Dialog title cannot be empty")

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise exceptions_validation.UserValidate("Dialog not found or not owned by user")

        dialog.title = normalized_title
        await session.commit()

        return {
            "dialog_id": str(dialog.dialog_id),
            "title": dialog.title,
        }


async def create_message(
    user_id: int,
    dialog_id: str,
    role: str,
    content: str,
    images: list[dict[str, str]] | None = None,
    attachments: list[dict[str, str | int]] | None = None,
):

    async with async_session() as session:
        sequence_index = await _next_dialog_sequence_index(session, user_id, dialog_id)
        new_message = Message(
            role=role,
            content=content,
            dialog_id=dialog_id,
            user_id=user_id,
            sequence_index=sequence_index,
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

        for attachment in attachments or []:
            attachment_id = attachment.get("attachment_id")
            try:
                normalized_attachment_id = int(attachment_id)
            except (TypeError, ValueError):
                continue

            attachment_stmt = select(Attachment).where(
                Attachment.attachment_id == normalized_attachment_id,
                Attachment.user_id == user_id,
            )
            attachment_result = await session.execute(attachment_stmt)
            existing_attachment = attachment_result.scalar_one_or_none()
            if existing_attachment is None:
                continue

            session.add(
                MessageAttachment(
                    message_id=message_id,
                    attachment_id=normalized_attachment_id,
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
            .order_by(Message.sequence_index.asc(), Message.message_id.asc())
            .limit(1000)
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        message_ids = [m.message_id for m in messages if m.message_id is not None]
        images_by_message: dict[int, list[dict[str, str]]] = {}
        attachments_by_message: dict[int, list[dict[str, str | int]]] = {}
        if message_ids:
            images_by_message = await image_repository.load_message_images(
                session,
                message_ids=message_ids,
            )
            attachments_by_message = await attachment_repository.load_message_attachments(
                session,
                message_ids=message_ids,
            )

        combined_rows: list[tuple] = []
        for m in messages:
            assert m.created is not None
            message_id = m.message_id
            if message_id is None:
                continue
            if m.role not in {"user", "system"}:
                continue
            combined_rows.append(
                (
                    int(m.sequence_index),
                    {
                        "message_id": str(message_id),
                        "role": m.role,
                        "content": m.content,
                        "images": images_by_message.get(message_id, []),
                        "attachments": attachments_by_message.get(message_id, []),
                        "created": m.created.isoformat(),
                    },
                )
            )

        assistant_turn_stmt = (
            select(AssistantTurnEvent)
            .where(AssistantTurnEvent.dialog_id == dialog_id, AssistantTurnEvent.user_id == user_id)
            .order_by(
                AssistantTurnEvent.sequence_index.asc(),
                AssistantTurnEvent.assistant_turn_event_id.asc(),
            )
        )
        assistant_turn_result = await session.execute(assistant_turn_stmt)
        assistant_turn_events = assistant_turn_result.scalars().all()

        turns_by_id: dict[str, dict] = {}
        ordered_turn_ids: list[str] = []
        for event in assistant_turn_events:
            assert event.created is not None
            turn_id = str(event.turn_id or "").strip()
            if not turn_id:
                continue
            if turn_id not in turns_by_id:
                turns_by_id[turn_id] = {
                    "message_id": None,
                    "role": "assistant_turn",
                    "turn_id": turn_id,
                    "events": [],
                    "created": event.created.isoformat(),
                    "_sequence_index": int(event.sequence_index),
                }
                ordered_turn_ids.append(turn_id)
            turns_by_id[turn_id]["events"].append(
                {
                    "event_type": event.event_type,
                    "reasoning_text": event.reasoning_text,
                    "content_text": event.content_text,
                    "tool_call_id": event.tool_call_id,
                    "tool_name": event.tool_name,
                    "arguments_json": event.arguments_json,
                    "result_text": event.result_text,
                    "error_text": event.error_text,
                }
            )

        for turn_id in ordered_turn_ids:
            turn = turns_by_id[turn_id]
            combined_rows.append((int(turn.pop("_sequence_index")), turn))

        combined_rows.sort(key=lambda row: row[0])
        return [row[1] for row in combined_rows]


async def create_assistant_turn_events(
    user_id: int,
    dialog_id: str,
    turn_id: str,
    events: list[dict],
):
    normalized_turn_id = str(turn_id).strip()
    if not normalized_turn_id:
        raise exceptions_validation.UserValidate("turn_id is required")
    if not events:
        return

    async with async_session() as session:
        next_sequence_index = await _next_dialog_sequence_index_in_session(session, user_id, dialog_id)
        for event in events:
            event_type = str(event.get("event_type", "")).strip()
            if event_type not in {"assistant_segment", "tool_call"}:
                continue
            assistant_turn_event = AssistantTurnEvent(
                user_id=user_id,
                dialog_id=dialog_id,
                turn_id=normalized_turn_id,
                sequence_index=next_sequence_index,
                event_type=event_type,
                reasoning_text=str(event.get("reasoning_text", "")),
                content_text=str(event.get("content_text", "")),
                tool_call_id=str(event.get("tool_call_id", "")),
                tool_name=str(event.get("tool_name", "")),
                arguments_json=str(event.get("arguments_json", "{}")),
                result_text=str(event.get("result_text", "")),
                error_text=str(event.get("error_text", "")),
            )
            session.add(assistant_turn_event)
            next_sequence_index += 1
        await session.commit()


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
        sequence_index = await _next_dialog_sequence_index(session, user_id, dialog_id)
        event = ToolCallEvent(
            user_id=user_id,
            dialog_id=dialog_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            sequence_index=sequence_index,
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
            .where(
                Message.dialog_id == message.dialog_id,
                Message.sequence_index > message.sequence_index,
                Message.user_id == user_id,
            )
            .values(active=0)
        )
        await session.execute(deactivate_stmt)

        # Remove tool call events that belong to turns after the edited message.
        delete_tool_events_stmt = delete(ToolCallEvent).where(
            ToolCallEvent.dialog_id == message.dialog_id,
            ToolCallEvent.user_id == user_id,
            ToolCallEvent.sequence_index > message.sequence_index,
        )
        await session.execute(delete_tool_events_stmt)

        delete_assistant_turn_events_stmt = delete(AssistantTurnEvent).where(
            AssistantTurnEvent.dialog_id == message.dialog_id,
            AssistantTurnEvent.user_id == user_id,
            AssistantTurnEvent.sequence_index > message.sequence_index,
        )
        await session.execute(delete_assistant_turn_events_stmt)

        await session.commit()

        return {"message_id": message_id, "content": new_content, "updated": True}
