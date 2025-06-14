from starlette.requests import Request
from chat_client.database.cache import DatabaseCache
from chat_client.core.send_mail import send_smtp_message

# from chat_client.core.exceptions import UserValidate
from chat_client.core import exceptions_validation
from chat_client.core import user_session
from chat_client.repositories import token_repository
from chat_client.core.templates import get_template_content
from chat_client.models import User, UserToken
from data.config import HOSTNAME_WITH_SCHEME, SITE_NAME
import bcrypt
import logging
import secrets
import re
from chat_client.core import flash

from sqlalchemy import select
from chat_client.database.db_session import async_session

logger: logging.Logger = logging.getLogger(__name__)


# Utility Functions
def _password_hash(password: str, cost: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=cost)
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def _check_password(entered_password: str, stored_hashed_password: str) -> bool:
    return bcrypt.checkpw(entered_password.encode(), stored_hashed_password.encode())


def _verify_password(password: str, password_2: str):
    if password != password_2:
        raise exceptions_validation.UserValidate("Passwords do not match")
    if len(password) < 8:
        raise exceptions_validation.UserValidate("Password is too short")


def _is_valid_email(email: str):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise exceptions_validation.UserValidate("Invalid email")


async def _validate_captcha(request: Request):
    form = await request.form()
    captcha = str(form.get("captcha")).lower()
    captcha_session = str(request.session.get("captcha")).lower()
    if captcha != captcha_session:
        raise exceptions_validation.UserValidate("Invalid CAPTCHA")


# Main Logic
async def create_user(request: Request):
    form = await request.form()
    password = str(form.get("password"))
    password_2 = str(form.get("password_2"))
    email = str(form.get("email"))

    _is_valid_email(email)
    _verify_password(password, password_2)
    await _validate_captcha(request)

    password_hashed = _password_hash(password)

    async with async_session() as session:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise exceptions_validation.UserValidate("User already exists. Please login or reset your password.")

        token = await token_repository.create_token(session, "VERIFY")

        new_user = User(email=email, password_hash=password_hashed, random=token)
        session.add(new_user)
        await session.commit()

        context = {
            "subject": "Please verify your account",
            "email": email,
            "token": token,
            "user_row": {"user_id": new_user.user_id, "email": new_user.email},
            "site_name": SITE_NAME,
            "hostname_with_scheme": HOSTNAME_WITH_SCHEME,
        }
        message = await get_template_content("mails/verify_user.html", context)

        try:
            await send_smtp_message(email, context["subject"], message)
        except Exception:
            raise exceptions_validation.UserValidate("Failed to send reset email. Please try and sign up again later.")

        return {"user_id": new_user.user_id, "email": new_user.email}


async def verify_user(request: Request):
    form = await request.form()
    token = str(form.get("token"))

    async with async_session() as session:
        token_is_valid = await token_repository.validate_token(session, token, "VERIFY")
        if not token_is_valid:
            raise exceptions_validation.UserValidate("Token is expired. Please request a new password in order to verify your account.")

        stmt = select(User).where(User.random == token)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise exceptions_validation.UserValidate("User does not exist")
        if user.verified == 1:
            raise exceptions_validation.UserValidate("User is already verified")

        user.verified = 1
        await session.commit()


async def login_user(request: Request):
    json_data = await request.json()
    email = json_data.get("email")
    password = json_data.get("password")

    logging.info(f"Login attempt for email: {email}")

    async with async_session() as session:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise exceptions_validation.UserValidate("User does not exist")
        if user.verified == 0:
            raise exceptions_validation.UserValidate(
                "Your account is not verified. In order to verify your account, "
                "you should reset your password. When this is done, you are verified."
            )
        if not _check_password(password, user.password_hash):
            raise exceptions_validation.UserValidate("Invalid password")

        session_token = secrets.token_urlsafe(32)
        assert user.user_id is not None
        new_token = UserToken(token=session_token, user_id=user.user_id)

        session.add(new_token)
        await session.commit()

        user_session.set_user_session(request, user.user_id, session_token)
        return {"user_id": user.user_id, "email": user.email}


async def reset_password(request: Request):
    form = await request.form()
    email = str(form.get("email"))

    _is_valid_email(email)
    await _validate_captcha(request)

    async with async_session() as session:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise exceptions_validation.UserValidate("User does not exist")

        token = await token_repository.create_token(session, "RESET")
        user.random = token
        await session.commit()

        context = {
            "subject": "Please reset your password",
            "email": email,
            "token": token,
            "user_row": {"user_id": user.user_id, "email": user.email},
            "site_name": SITE_NAME,
            "hostname_with_scheme": HOSTNAME_WITH_SCHEME,
        }
        message = await get_template_content("mails/reset_password.html", context)

        try:
            await send_smtp_message(email, context["subject"], message)
        except Exception:
            raise exceptions_validation.UserValidate("Failed to send reset email. Please try and sign up again later.")


async def new_password(request: Request):
    form = await request.form()
    token = str(form.get("token"))
    password = str(form.get("password"))
    password_2 = str(form.get("password_2"))

    _verify_password(password, password_2)

    async with async_session() as session:
        token_is_valid = await token_repository.validate_token(session, token, "RESET")
        if not token_is_valid:
            raise exceptions_validation.UserValidate("Token is expired. Please request a new password again")

        stmt = select(User).where(User.random == token)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise exceptions_validation.UserValidate("User does not exist")

        user.password_hash = _password_hash(password)
        user.verified = 1
        user.random = secrets.token_urlsafe(32)
        await session.commit()


async def update_profile(request: Request):
    user_id = await user_session.is_logged_in(request)
    if not user_id:
        raise exceptions_validation.UserValidate("You must be logged in to update your profile")

    form_data = await request.json()

    allowed_fields = {"username", "dark_theme", "system_message"}
    if not allowed_fields.issuperset(form_data.keys()):
        raise exceptions_validation.UserValidate("Invalid form fields")

    async with async_session() as session:
        cache = DatabaseCache(session)
        cache_key = f"user_{user_id}"
        await cache.set(cache_key, form_data)


async def get_profile(user_id: int):
    if not user_id:
        return {}

    async with async_session() as session:
        cache = DatabaseCache(session)
        cache_key = f"user_{user_id}"
        profile = await cache.get(cache_key)
        if not profile:
            profile = {}
        return profile
