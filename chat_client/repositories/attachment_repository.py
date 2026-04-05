from sqlalchemy import distinct, select, update

from chat_client.core import exceptions_validation
from chat_client.database.db_session import async_session
from chat_client.models import Attachment, Message, MessageAttachment


def _serialize_attachment(attachment: Attachment) -> dict[str, str | int]:
    return {
        "attachment_id": int(attachment.attachment_id or 0),
        "name": attachment.name,
        "content_type": attachment.content_type,
        "size_bytes": int(attachment.size_bytes or 0),
        "storage_path": attachment.storage_path,
    }


async def create_attachment(
    user_id: int,
    name: str,
    content_type: str,
    size_bytes: int,
    storage_path: str,
):
    async with async_session() as session:
        attachment = Attachment(
            user_id=user_id,
            name=name,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )
        session.add(attachment)
        await session.commit()
        await session.refresh(attachment)
        return attachment.attachment_id


async def update_attachment_storage_path(user_id: int, attachment_id: int, storage_path: str):
    async with async_session() as session:
        stmt = (
            update(Attachment)
            .where(Attachment.attachment_id == attachment_id, Attachment.user_id == user_id)
            .values(storage_path=storage_path)
        )
        await session.execute(stmt)
        await session.commit()


async def get_attachment(user_id: int, attachment_id: int) -> dict[str, str | int]:
    async with async_session() as session:
        stmt = select(Attachment).where(Attachment.attachment_id == attachment_id, Attachment.user_id == user_id)
        result = await session.execute(stmt)
        attachment = result.scalar_one_or_none()
        if attachment is None:
            raise exceptions_validation.UserValidate("Attachment not found or not owned by user")
        return _serialize_attachment(attachment)


async def get_attachments(user_id: int, attachment_ids: list[int]) -> list[dict[str, str | int]]:
    normalized_ids = []
    for attachment_id in attachment_ids:
        try:
            normalized_ids.append(int(attachment_id))
        except (TypeError, ValueError):
            continue
    if not normalized_ids:
        return []

    async with async_session() as session:
        stmt = (
            select(Attachment)
            .where(Attachment.user_id == user_id, Attachment.attachment_id.in_(normalized_ids))
            .order_by(Attachment.attachment_id.asc())
        )
        result = await session.execute(stmt)
        attachments = result.scalars().all()
        attachments_by_id = {int(attachment.attachment_id or 0): _serialize_attachment(attachment) for attachment in attachments}

    missing_ids = [attachment_id for attachment_id in normalized_ids if attachment_id not in attachments_by_id]
    if missing_ids:
        raise exceptions_validation.UserValidate("One or more attachments were not found.")

    return [attachments_by_id[attachment_id] for attachment_id in normalized_ids]


async def load_message_attachments(
    session,
    *,
    message_ids: list[int],
) -> dict[int, list[dict[str, str | int]]]:
    if not message_ids:
        return {}

    stmt = (
        select(
            MessageAttachment.message_id,
            Attachment.attachment_id,
            Attachment.name,
            Attachment.content_type,
            Attachment.size_bytes,
        )
        .join(Attachment, Attachment.attachment_id == MessageAttachment.attachment_id)
        .where(MessageAttachment.message_id.in_(message_ids))
        .order_by(MessageAttachment.message_attachment_id.asc())
    )
    result = await session.execute(stmt)

    attachments_by_message: dict[int, list[dict[str, str | int]]] = {}
    for message_id, attachment_id, name, content_type, size_bytes in result.all():
        attachments_by_message.setdefault(message_id, []).append(
            {
                "attachment_id": int(attachment_id),
                "name": str(name),
                "content_type": str(content_type or ""),
                "size_bytes": int(size_bytes or 0),
            }
        )
    return attachments_by_message


async def get_dialog_attachment_ids(user_id: int, dialog_id: str) -> list[int]:
    async with async_session() as session:
        stmt = (
            select(distinct(MessageAttachment.attachment_id))
            .join(Message, Message.message_id == MessageAttachment.message_id)
            .where(
                Message.user_id == user_id,
                Message.dialog_id == dialog_id,
                Message.active == 1,
            )
            .order_by(MessageAttachment.attachment_id.asc())
        )
        result = await session.execute(stmt)
        return [int(attachment_id) for attachment_id in result.scalars().all() if attachment_id is not None]
