from sqlalchemy import select

from chat_client.models import Image, MessageImage


async def load_message_images(
    session,
    *,
    message_ids: list[int],
) -> dict[int, list[dict[str, str]]]:
    if not message_ids:
        return {}

    stmt = (
        select(MessageImage.message_id, Image.data_url)
        .join(Image, Image.image_id == MessageImage.image_id)
        .where(MessageImage.message_id.in_(message_ids))
        .order_by(MessageImage.message_image_id.asc())
    )
    result = await session.execute(stmt)

    images_by_message: dict[int, list[dict[str, str]]] = {}
    for message_id, data_url in result.all():
        images_by_message.setdefault(message_id, []).append({"data_url": data_url})
    return images_by_message
