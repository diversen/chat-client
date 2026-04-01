"""Add attachment and message_attachment tables

Revision ID: a1b2c3d4e5f6
Revises: 7a1b2c3d4e5f
Create Date: 2026-04-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "attachment",
        sa.Column("attachment_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("created", sa.TIMESTAMP(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("attachment_id"),
        sqlite_autoincrement=True,
    )
    op.create_index("attachment_user_id", "attachment", ["user_id"], unique=False)

    op.create_table(
        "message_attachment",
        sa.Column("message_attachment_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("created", sa.TIMESTAMP(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachment.attachment_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["message.message_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_attachment_id"),
        sqlite_autoincrement=True,
    )
    op.create_index("message_attachment_message_id", "message_attachment", ["message_id"], unique=False)
    op.create_index("message_attachment_attachment_id", "message_attachment", ["attachment_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("message_attachment_attachment_id", table_name="message_attachment")
    op.drop_index("message_attachment_message_id", table_name="message_attachment")
    op.drop_table("message_attachment")
    op.drop_index("attachment_user_id", table_name="attachment")
    op.drop_table("attachment")
