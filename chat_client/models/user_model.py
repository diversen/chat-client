from starlette.requests import Request
from chat_client.database.crud import CRUD
from chat_client.database.database_utils import DatabaseConnection
from chat_client.database.cache import DatabaseCache
from chat_client.core.send_mail import send_smtp_message
from chat_client.core.exceptions import UserValidate
from chat_client.core import session
from chat_client.models import token_model
from chat_client.core.templates import get_template_content
from config import HOSTNAME_WITH_SCHEME, SITE_NAME, DATABASE
import bcrypt
import logging
import secrets
import re


logger: logging.Logger = logging.getLogger(__name__)


def _password_hash(password: str, cost: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=cost)
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def _check_password(entered_password: str, stored_hashed_password: str) -> bool:
    return bcrypt.checkpw(entered_password.encode(), stored_hashed_password.encode())


def _verify_password(password: str, password_2: str):
    if password != password_2:
        raise UserValidate("Passwords do not match")

    if len(password) < 8:
        raise UserValidate("Password is too short")


def _is_valid_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise UserValidate("Invalid email")


async def _validate_captcha(request: Request):
    form = await request.form()

    captcha = str(form.get("captcha")).lower()
    captcha_session = str(request.session.get("captcha")).lower()

    if captcha != captcha_session:
        raise UserValidate("Invalid CAPTCHA")


async def create_user(request: Request):
    form = await request.form()

    password = str(form.get("password"))
    password_2 = str(form.get("password_2"))
    email = str(form.get("email"))

    # validate form values
    _is_valid_email(email)
    _verify_password(password, password_2)
    await _validate_captcha(request)

    password_hash = _password_hash(password)
    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)

        # Check if user with email already exists
        values = {"email": email}
        if await crud.exists("users", values):
            raise UserValidate("User already exists. Please login or reset your password.")

        # Generate random token
        token = await token_model.create_token(crud, "VERIFY")

        # Insert User
        insert_values = {
            "email": email,
            "password_hash": password_hash,
            "random": token,
        }

        await crud.insert("users", insert_values=insert_values)

        # Get user
        user_row = await crud.select_one("users", filters=values)
        context = {
            "subject": "Please verify your account",
            "email": email,
            "token": token,
            "user_row": user_row,
            "site_name": SITE_NAME,
            "hostname_with_scheme": HOSTNAME_WITH_SCHEME,
        }
        message = await get_template_content("mails/verify_user.html", context)

        # Send email
        try:
            await send_smtp_message(email, context["subject"], message)
        except Exception:
            raise UserValidate("Failed to send reset email. Please try and sign up again later.")

        return user_row


async def verify_user(request):
    form = await request.form()
    token = form.get("token")

    # Update user
    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)

        token_is_valid = await token_model.validate_token(crud, token, "VERIFY")
        if not token_is_valid:
            raise UserValidate("Token is expired. Please request a new password in order to verify your account.")

        user_row = await crud.select_one(
            "users",
            filters={
                "random": token,
            },
        )

        if not user_row:
            raise UserValidate("User does not exist")

        if user_row["verified"] == 1:
            raise UserValidate("User is already verified")

        update_values = {"verified": 1}
        filters = {"user_id": user_row["user_id"]}
        await crud.update("users", update_values, filters=filters)


async def login_user(request: Request):
    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)

        json_data = await request.json()
        email = json_data.get("email")
        password = json_data.get("password")

        # Get user
        user_row = await crud.select_one(
            "users",
            filters={
                "email": email,
            },
        )

        # check password
        if not user_row:
            raise UserValidate("User does not exist")
        if user_row["verified"] == 0:
            raise UserValidate(
                "Your account is not verified. In order to verify your account, "
                "you should reset your password. When this is done, you are verified."
            )
        if not _check_password(password, user_row["password_hash"]):
            raise UserValidate("Invalid password")

        # Get session token
        session_token = secrets.token_urlsafe(32)
        insert_values = {
            "token": session_token,
            "user_id": user_row["user_id"],
        }
        await crud.insert("user_token", insert_values=insert_values)
        session.set_user_session(request, user_row["user_id"], session_token)

        return user_row


async def reset_password(request: Request):
    form = await request.form()
    email = form.get("email")

    _is_valid_email(email)
    await _validate_captcha(request)

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)

        # Check if user already exists
        values = {"email": email}
        user_row = await crud.select_one("users", filters=values)
        if not user_row:
            raise UserValidate("User does not exist")

        # Generate random token
        token = await token_model.create_token(crud, "RESET")

        # Update User
        update_values = {"random": token}
        filters = {"user_id": user_row["user_id"]}
        await crud.update("users", update_values, filters=filters)

        # Generate email message
        context = {
            "subject": "Please reset your password",
            "email": email,
            "token": token,
            "user_row": user_row,
            "site_name": SITE_NAME,
            "hostname_with_scheme": HOSTNAME_WITH_SCHEME,
        }
        message = await get_template_content("mails/reset_password.html", context)

        # Send email
        try:
            await send_smtp_message(email, context["subject"], message)
        except Exception:
            raise UserValidate("Failed to send reset email. Please try and sign up again later.")


async def new_password(request: Request):
    form = await request.form()
    token = str(form.get("token"))
    password = str(form.get("password"))
    password_2 = str(form.get("password_2"))

    _verify_password(password, password_2)

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        crud = CRUD(connection)

        token_is_valid = await token_model.validate_token(crud, token, "RESET")
        if not token_is_valid:
            raise UserValidate("Token is expired. Please request a new password again")

        # Check if user already exists
        user_row = await crud.select_one(
            "users",
            filters={
                "random": token,
            },
        )
        if not user_row:
            raise UserValidate("User does not exist")

        # Update User
        update_values = {
            "password_hash": _password_hash(password),
            "verified": 1,
            "random": secrets.token_urlsafe(32),
        }
        filters = {"user_id": user_row["user_id"]}
        await crud.update("users", update_values, filters=filters)


async def update_profile(request: Request):
    """
    Update the user profile
    """
    user_id = await session.is_logged_in(request)
    if not user_id:
        raise UserValidate("You must be logged in to update your profile")

    form_data = await request.json()

    # allowed form fields
    allowed_fields = ["username", "dark_theme", "system_message"]
    if not set(allowed_fields).issuperset(form_data.keys()):
        raise UserValidate("Invalid form fields")

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        cache = DatabaseCache(connection)

        cache_key = f"user_{user_id}"
        await cache.set(cache_key, form_data)


async def get_profile(user_id: int):
    """
    Get the user profile dict or an empty dict if the user is not logged in
    """

    if not user_id:
        return {}

    database_connection = DatabaseConnection(DATABASE)
    async with database_connection.async_transaction_scope() as connection:
        cache = DatabaseCache(connection)

        cache_key = f"user_{user_id}"
        profile = await cache.get(cache_key)
        if not profile:
            profile = {}
        return profile
