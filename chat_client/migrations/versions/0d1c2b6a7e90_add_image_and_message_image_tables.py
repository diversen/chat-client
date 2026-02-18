"""Add image and message_image tables

Revision ID: 0d1c2b6a7e90
Revises: 6c84ab6b0853
Create Date: 2026-02-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0d1c2b6a7e90"
down_revision: Union[str, None] = "6c84ab6b0853"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "image",
        sa.Column("image_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("data_url", sa.Text(), nullable=False),
        sa.Column("created", sa.TIMESTAMP(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("image_id"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "message_image",
        sa.Column("message_image_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column("created", sa.TIMESTAMP(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["image.image_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["message.message_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_image_id"),
        sqlite_autoincrement=True,
    )
    op.create_index("message_image_image_id", "message_image", ["image_id"], unique=False)
    op.create_index("message_image_message_id", "message_image", ["message_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("message_image_message_id", table_name="message_image")
    op.drop_index("message_image_image_id", table_name="message_image")
    op.drop_table("message_image")
    op.drop_table("image")
