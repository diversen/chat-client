from starlette.requests import Request
from starlette.responses import JSONResponse
from chat_client.core.exceptions import UserValidate
from chat_client.core import user_session
from chat_client.core.exceptions import JSONError
from chat_client.models import Dialog, Message
from chat_client.database.db_session import async_session  # global session
import uuid
import logging
from sqlalchemy import select, func

logger: logging.Logger = logging.getLogger(__name__)

DIALOGS_PER_PAGE = 10


async def create_dialog(request: Request):
    form_data = await request.json()
    title = str(form_data.get("title"))
    user_id = await user_session.is_logged_in(request)

    if not user_id:
        return JSONResponse({"error": "You must be logged in to save a dialog"})

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


async def create_message(request: Request):
    form_data = await request.json()

    dialog_id = request.path_params.get("dialog_id")
    content = str(form_data.get("content"))
    role = str(form_data.get("role"))
    user_id = await user_session.is_logged_in(request)

    if not user_id:
        return JSONResponse({"error": True, "message": "You must be logged in to save a message"})

    async with async_session() as session:
        new_message = Message(
            role=role,
            content=content,
            dialog_id=dialog_id,
            user_id=user_id,
        )
        session.add(new_message)
        await session.commit()


async def get_dialog(request: Request):
    dialog_id = request.path_params.get("dialog_id")
    user_id = await user_session.is_logged_in(request)

    if not user_id:
        raise UserValidate("You must be logged in to get a dialog")

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise UserValidate("Dialog not found or not owned by user")

        return {
            "dialog_id": str(dialog.dialog_id),
            "title": dialog.title,
            "created": dialog.created.isoformat(),
        }


async def get_messages(request: Request):
    dialog_id = request.path_params.get("dialog_id")
    user_id = await user_session.is_logged_in(request)

    if not user_id:
        return JSONResponse({"error": "You must be logged in to get messages"})

    async with async_session() as session:
        stmt = select(Message).where(Message.dialog_id == dialog_id, Message.user_id == user_id).order_by(Message.created.asc()).limit(1000)
        result = await session.execute(stmt)
        messages = result.scalars().all()

        return [
            {
                "message_id": str(m.message_id),
                "role": m.role,
                "content": m.content,
                "created": m.created.isoformat(),
            }
            for m in messages
        ]


async def delete_dialog(request: Request):
    user_id = await user_session.is_logged_in(request)
    dialog_id = request.path_params.get("dialog_id")

    if not user_id:
        raise UserValidate("You must be logged in to delete a dialog")

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise UserValidate("Dialog is not connected to user. You can't delete it")

        await session.delete(dialog)
        await session.commit()


async def get_dialogs_info(request: Request):
    current_page = int(request.query_params.get("page", 1))
    user_id = await user_session.is_logged_in(request)

    if not user_id:
        raise JSONError("It seems you have been logged out. Log in again", status_code=200)

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

        return {
            "current_page": current_page,
            "per_page": DIALOGS_PER_PAGE,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_page": prev_page,
            "next_page": next_page,
            "dialogs": [
                {
                    "dialog_id": str(d.dialog_id),  # UUID -> string
                    "title": d.title,
                    "created": d.created.isoformat(),  # datetime -> ISO string
                }
                for d in dialogs
            ],
            "num_dialogs": num_dialogs,
        }
