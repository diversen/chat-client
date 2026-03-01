from datetime import datetime
from sqlalchemy import Text, String, ForeignKey, TIMESTAMP, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Mapped, mapped_column


class Base(MappedAsDataclass, DeclarativeBase):
    pass


created: Mapped[datetime | None] = mapped_column(
    TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
)


class Cache(Base):
    __tablename__ = "cache"
    __table_args__ = {"sqlite_autoincrement": True}

    cache_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    unix_timestamp: Mapped[int] = mapped_column(default=0)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_random", "random"),
        Index("idx_users_password_hash", "password_hash"),
        {"sqlite_autoincrement": True},
    )

    user_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    random: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
    )
    verified: Mapped[int] = mapped_column(default=0)
    locked: Mapped[int] = mapped_column(default=0)


class UserToken(Base):
    __tablename__ = "user_token"
    __table_args__ = (
        Index("idx_user_token_user_id", "user_id"),
        Index("idx_user_token_token", "token"),
        {"sqlite_autoincrement": True},
    )

    user_token_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
    )
    expires: Mapped[int] = mapped_column(default=0)


class Token(Base):
    __tablename__ = "token"
    __table_args__ = {"sqlite_autoincrement": True}

    token_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
    )


class ACL(Base):
    __tablename__ = "acl"
    __table_args__ = (
        Index("idx_acl_user_id", "user_id"),
        Index("idx_acl_role", "role"),
        Index("idx_acl_entity_id", "entity_id"),
        {"sqlite_autoincrement": True},
    )

    acl_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(nullable=True)


class Dialog(Base):
    __tablename__ = "dialog"
    __table_args__ = (
        Index("dialog_user_id", "user_id"),
        {"sqlite_autoincrement": True},
    )

    dialog_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
    )
    public: Mapped[int] = mapped_column(default=0)


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (
        Index("message_dialog_id", "dialog_id"),
        Index("message_user_id", "user_id"),
        Index("message_dialog_sequence_index", "dialog_id", "sequence_index"),
        {"sqlite_autoincrement": True},
    )

    message_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    dialog_id: Mapped[str] = mapped_column(ForeignKey("dialog.dialog_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_index: Mapped[int] = mapped_column(nullable=False, default=0)
    active: Mapped[int] = mapped_column(default=1)
    created: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
    )


class Image(Base):
    __tablename__ = "image"
    __table_args__ = {"sqlite_autoincrement": True}

    image_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    data_url: Mapped[str] = mapped_column(Text, nullable=False)
    created: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
    )


class MessageImage(Base):
    __tablename__ = "message_image"
    __table_args__ = (
        Index("message_image_message_id", "message_id"),
        Index("message_image_image_id", "image_id"),
        {"sqlite_autoincrement": True},
    )

    message_image_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    message_id: Mapped[int] = mapped_column(ForeignKey("message.message_id", ondelete="CASCADE"), nullable=False)
    image_id: Mapped[int] = mapped_column(ForeignKey("image.image_id", ondelete="CASCADE"), nullable=False)
    created: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
    )


class ToolCallEvent(Base):
    __tablename__ = "tool_call_event"
    __table_args__ = (
        Index("tool_call_event_dialog_id", "dialog_id"),
        Index("tool_call_event_user_id", "user_id"),
        Index("tool_call_event_tool_call_id", "tool_call_id"),
        Index("tool_call_event_dialog_sequence_index", "dialog_id", "sequence_index"),
        {"sqlite_autoincrement": True},
    )

    tool_call_event_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    dialog_id: Mapped[str] = mapped_column(ForeignKey("dialog.dialog_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    tool_call_id: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_index: Mapped[int] = mapped_column(nullable=False, default=0)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False, init=False
    )


class Prompt(Base):
    __tablename__ = "prompt"
    __table_args__ = (
        Index("idx_prompt_user_id", "user_id"),
        {"sqlite_autoincrement": True},
    )

    prompt_id: Mapped[int | None] = mapped_column(primary_key=True, autoincrement=True, init=False)
    title: Mapped[str] = mapped_column(Text(length=256), nullable=False)
    prompt: Mapped[str] = mapped_column(Text(length=8096), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
