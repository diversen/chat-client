"""
Generate a dialog model for the chatbot

Sqlite3 database schema for dialog model with uuid as primary key

Two tables: dialogs and messages

-- dialog table
CREATE TABLE dialog (
  dialog_id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES user(id)
);

-- message table with ON DELETE CASCADE
CREATE TABLE message (
  message_id INTEGER PRIMARY KEY,
  dialog_id TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  message TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (dialog_id) REFERENCES dialog(dialog_id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES user(id)
);

-- indexes for faster lookups
CREATE INDEX dialog_user_id ON dialog(user_id);
CREATE INDEX message_dialog_id ON message(dialog_id);
CREATE INDEX message_user_id ON message(user_id);

"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from chat_client.database.crud import CRUD
from chat_client.database.database_utils import DatabaseConnection
from chat_client.core.exceptions import UserValidate
from chat_client.core import session
from chat_client.core.exceptions import JSONError
from config import DATABASE
import uuid
import logging


logger: logging.Logger = logging.getLogger(__name__)


async def create_dialog(request: Request):
    form_data = await request.json()
    title = str(form_data.get("title"))
    user_id = await session.is_logged_in(request)
    if not user_id:
        return JSONResponse({"error": "You must be logged in to save a dialog"})

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)
        dialog_id = str(uuid.uuid4())
        await crud.insert(
            "dialog",
            {
                "dialog_id": dialog_id,
                "user_id": user_id,
                "title": title,
            },
        )

        return dialog_id


async def create_message(request: Request):
    form_data = await request.json()

    # get dialog_id from path param
    dialog_id = request.path_params.get("dialog_id")
    content = str(form_data.get("content"))
    role = str(form_data.get("role"))
    user_id = await session.is_logged_in(request)

    if not user_id:
        return JSONResponse({"error": True, "message": "You must be logged in to save a message"})

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)

        # Check if user owns dialog
        await crud.insert(
            "message",
            {
                "role": role,
                "content": content,
                "dialog_id": dialog_id,
                "user_id": user_id,
            },
        )


async def get_dialog(request: Request):
    dialog_id = request.path_params.get("dialog_id")
    user_id = await session.is_logged_in(request)
    if not user_id:
        raise UserValidate("You must be logged in to get a dialog")

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)
        dialog = await crud.select_one(
            table="dialog",
            filters={
                "dialog_id": dialog_id,
                "user_id": user_id,
            },
        )

        return dialog


async def get_messages(request: Request):
    dialog_id = request.path_params.get("dialog_id")
    user_id = await session.is_logged_in(request)
    if not user_id:
        return JSONResponse({"error": "You must be logged in to get messages"})

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)
        # check user owns dialog
        messages = await crud.select(
            table="message",
            filters={
                "dialog_id": dialog_id,
                "user_id": user_id,
            },
            order_by=[("created", "ASC")],
            # Some kind of hard limit
            limit_offset=(1000, 0),
        )

        return messages


async def delete_dialog(request: Request):
    user_id = await session.is_logged_in(request)
    dialog_id = request.path_params.get("dialog_id")
    if not user_id:
        raise UserValidate("You must be logged in to delete a dialog")

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)

        # Get dialog
        dialog = await crud.select_one(
            table="dialog",
            filters={
                "dialog_id": dialog_id,
                "user_id": user_id,
            },
        )

        if not dialog:
            raise UserValidate("Dialog is not connected to user. You can't delete it")

        await crud.delete(
            table="dialog",
            filters={
                "dialog_id": dialog_id,
                "user_id": user_id,
            },
        )


async def _num_dialogs(crud: CRUD, user_id: int) -> int:
    return await crud.count(
        table="dialog",
        filters={
            "user_id": user_id,
        },
    )


DIALOGS_PER_PAGE = 10


async def get_dialogs_info(request: Request):
    current_page = int(request.query_params.get("page", 1))
    user_id = await session.is_logged_in(request)
    if not user_id:
        raise JSONError("It seems you have been logged out. Log in again", status_code=200)

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)

        dialogs = await crud.select(
            table="dialog",
            filters={
                "user_id": user_id,
            },
            order_by=[("created", "DESC")],
            limit_offset=(DIALOGS_PER_PAGE, (current_page - 1) * DIALOGS_PER_PAGE),
        )

        num_dialogs = await _num_dialogs(crud, user_id)
        has_prev = current_page > 1
        has_next = num_dialogs > current_page * DIALOGS_PER_PAGE

        if has_prev:
            prev_page = current_page - 1
        else:
            prev_page = 0

        if has_next:
            next_page = current_page + 1
        else:
            next_page = 0

        return {
            "current_page": current_page,
            "per_page": DIALOGS_PER_PAGE,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_page": prev_page,
            "next_page": next_page,
            "dialogs": dialogs,
            "num_dialogs": num_dialogs,
        }
