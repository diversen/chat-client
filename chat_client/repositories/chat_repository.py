from starlette.requests import Request
from chat_client.core import exceptions_validation

from chat_client.models import Dialog, Message
from chat_client.database.db_session import async_session
import uuid
import logging
from sqlalchemy import select, func, update

logger: logging.Logger = logging.getLogger(__name__)

DIALOGS_PER_PAGE = 10


async def create_dialog(user_id: int, request: Request):
    form_data = await request.json()
    title = str(form_data.get("title"))

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


async def create_message(user_id: int, request: Request):
    form_data = await request.json()

    dialog_id = str(request.path_params.get("dialog_id"))
    content = str(form_data.get("content"))
    role = str(form_data.get("role"))

    async with async_session() as session:
        new_message = Message(
            role=role,
            content=content,
            dialog_id=dialog_id,
            user_id=user_id,
        )
        session.add(new_message)
        await session.commit()
        await session.refresh(new_message)
        
        return new_message.message_id


async def get_dialog(user_id: int, request: Request):
    dialog_id = request.path_params.get("dialog_id")

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


async def get_messages(user_id: int, request: Request):
    dialog_id = request.path_params.get("dialog_id")

    async with async_session() as session:
        stmt = (
            select(Message)
            .where(Message.dialog_id == dialog_id, Message.user_id == user_id, Message.active == 1)
            .order_by(Message.created.asc())
            .limit(1000)
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        return_list = []
        for m in messages:
            assert m.created is not None
            return_list.append(
                {
                    "message_id": str(m.message_id),
                    "role": m.role,
                    "content": m.content,
                    "created": m.created.isoformat(),
                }
            )

        return return_list


async def delete_dialog(user_id: int, request: Request):
    dialog_id = request.path_params.get("dialog_id")

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise exceptions_validation.UserValidate("Dialog is not connected to user. You can't delete it")

        await session.delete(dialog)
        await session.commit()


async def get_dialogs_info(user_id: int, request: Request):
    current_page = int(request.query_params.get("page", 1))

    async with async_session() as session:

        # Fetch dialogs for the current page
        stmt = (
            select(Dialog)
            .where(Dialog.user_id == user_id)
            .order_by(Dialog.created.desc())
            .limit(DIALOGS_PER_PAGE)
            .offset((current_page - 1) * DIALOGS_PER_PAGE)
        )
        result = await session.execute(stmt)
        dialogs = result.scalars().all()

        # Count total number of dialogs
        count_stmt = select(func.count()).select_from(Dialog).where(Dialog.user_id == user_id)
        count_result = await session.execute(count_stmt)
        num_dialogs = count_result.scalar_one()

        has_prev = current_page > 1
        has_next = num_dialogs > current_page * DIALOGS_PER_PAGE
        prev_page = current_page - 1 if has_prev else 0
        next_page = current_page + 1 if has_next else 0

        logger.warning(f"Dialogs for user {user_id}: {len(dialogs)} found on page {current_page}")

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


async def update_message(user_id: int, request: Request):
    """
    Update a message and deactivate newer messages in the same dialog
    """
    message_id = int(request.path_params.get("message_id"))
    form_data = await request.json()
    new_content = str(form_data.get("content", "")).strip()

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
                Message.created > message.created,
                Message.user_id == user_id
            )
            .values(active=0)
        )
        await session.execute(deactivate_stmt)

        await session.commit()

        return {
            "message_id": message_id,
            "content": new_content,
            "updated": True
        }
