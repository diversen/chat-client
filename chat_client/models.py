from sqlalchemy import Table, Column, Integer, String, Text, ForeignKey, Index, TIMESTAMP, create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_random", "random"),
        Index("idx_users_password_hash", "password_hash"),
        {"sqlite_autoincrement": True},
    )

    user_id = Column(Integer, primary_key=True)
    password_hash = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    created = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False)
    verified = Column(Integer, default=0)
    random = Column(Text, nullable=False)
    locked = Column(Integer, default=0)


class UserToken(Base):
    __tablename__ = "user_token"
    __table_args__ = (
        Index("idx_user_token_user_id", "user_id"),
        Index("idx_user_token_token", "token"),
        {"sqlite_autoincrement": True},
    )

    user_token_id = Column(Integer, primary_key=True)
    token = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    last_login = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False)
    expires = Column(Integer, default=0)


class Token(Base):
    __tablename__ = "token"
    __table_args__ = {"sqlite_autoincrement": True}

    token_id = Column(Integer, primary_key=True)
    token = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    created = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False)


class ACL(Base):
    __tablename__ = "acl"
    __table_args__ = (
        Index("idx_acl_user_id", "user_id"),
        Index("idx_acl_role", "role"),
        Index("idx_acl_entity_id", "entity_id"),
        {"sqlite_autoincrement": True},
    )

    acl_id = Column(Integer, primary_key=True)
    role = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(Integer, nullable=True)


class Cache(Base):
    __tablename__ = "cache"
    __table_args__ = {"sqlite_autoincrement": True}

    cache_id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, nullable=False, index=True)
    value = Column(Text, nullable=True)
    unix_timestamp = Column(Integer, default=0)


class Dialog(Base):
    __tablename__ = "dialog"
    __table_args__ = (
        Index("dialog_user_id", "user_id"),
        {"sqlite_autoincrement": True},
    )

    dialog_id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    created = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False)
    public = Column(Integer, default=0)


class Message(Base):
    __tablename__ = "message"
    __table_args__ = (
        Index("message_dialog_id", "dialog_id"),
        Index("message_user_id", "user_id"),
        {"sqlite_autoincrement": True},
    )

    message_id = Column(Integer, primary_key=True)
    dialog_id = Column(String, ForeignKey("dialog.dialog_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    created = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), nullable=False)


class Prompt(Base):
    __tablename__ = "prompt"
    __table_args__ = (
        Index("idx_prompt_user_id", "user_id"),
        {"sqlite_autoincrement": True},
    )

    prompt_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text(length=256), nullable=False)
    prompt = Column(Text(length=8096), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
