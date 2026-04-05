from sqlalchemy import select

from chat_client.core.attachments import parse_image_attachment_ref
from chat_client.models import Attachment, Image, MessageImage


async def load_message_images(
    session,
    *,
    message_ids: list[int],
) -> dict[int, list[dict[str, str | int]]]:
    if not message_ids:
        return {}

    stmt = (
        select(MessageImage.message_id, Image.data_url)
        .join(Image, Image.image_id == MessageImage.image_id)
        .where(MessageImage.message_id.in_(message_ids))
        .order_by(MessageImage.message_image_id.asc())
    )
    result = await session.execute(stmt)

    raw_images: list[tuple[int, str]] = [(int(message_id), str(data_url or "")) for message_id, data_url in result.all()]
    attachment_ids = {
        attachment_id
        for _, data_url in raw_images
        for attachment_id in [parse_image_attachment_ref(data_url)]
        if attachment_id is not None
    }

    attachments_by_id: dict[int, Attachment] = {}
    if attachment_ids:
        attachment_stmt = select(Attachment).where(Attachment.attachment_id.in_(attachment_ids))
        attachment_result = await session.execute(attachment_stmt)
        attachments_by_id = {
            int(attachment.attachment_id or 0): attachment
            for attachment in attachment_result.scalars().all()
            if attachment.attachment_id is not None
        }

    images_by_message: dict[int, list[dict[str, str | int]]] = {}
    for message_id, data_url in raw_images:
        attachment_id = parse_image_attachment_ref(data_url)
        if attachment_id is not None:
            attachment = attachments_by_id.get(attachment_id)
            if attachment is None:
                continue
            images_by_message.setdefault(message_id, []).append(
                {
                    "attachment_id": attachment_id,
                    "name": str(attachment.name or ""),
                    "content_type": str(attachment.content_type or ""),
                    "size_bytes": int(attachment.size_bytes or 0),
                    "preview_url": f"/api/chat/attachments/{attachment_id}/preview",
                }
            )
            continue
        images_by_message.setdefault(message_id, []).append({"data_url": data_url})
    return images_by_message
