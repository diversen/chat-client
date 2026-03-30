"""Add assistant_turn_event table

Revision ID: 7a1b2c3d4e5f
Revises: 9f4a7b5c2d10
Create Date: 2026-03-30 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "9f4a7b5c2d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "assistant_turn_event",
        sa.Column("assistant_turn_event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dialog_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.Text(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("reasoning_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("tool_call_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("tool_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("arguments_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dialog_id"], ["dialog.dialog_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("assistant_turn_event_id"),
        sqlite_autoincrement=True,
    )
    op.create_index("assistant_turn_event_dialog_id", "assistant_turn_event", ["dialog_id"], unique=False)
    op.create_index("assistant_turn_event_user_id", "assistant_turn_event", ["user_id"], unique=False)
    op.create_index(
        "assistant_turn_event_dialog_sequence_index",
        "assistant_turn_event",
        ["dialog_id", "sequence_index"],
        unique=False,
    )
    op.create_index(
        "assistant_turn_event_dialog_turn_id",
        "assistant_turn_event",
        ["dialog_id", "turn_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("assistant_turn_event_dialog_turn_id", table_name="assistant_turn_event")
    op.drop_index("assistant_turn_event_dialog_sequence_index", table_name="assistant_turn_event")
    op.drop_index("assistant_turn_event_user_id", table_name="assistant_turn_event")
    op.drop_index("assistant_turn_event_dialog_id", table_name="assistant_turn_event")
    op.drop_table("assistant_turn_event")
