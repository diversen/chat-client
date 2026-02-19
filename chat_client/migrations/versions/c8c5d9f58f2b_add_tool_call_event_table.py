"""Add tool_call_event table

Revision ID: c8c5d9f58f2b
Revises: 6c84ab6b0853, 0d1c2b6a7e90
Create Date: 2026-02-19 19:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8c5d9f58f2b"
down_revision: Union[str, Sequence[str], None] = ("6c84ab6b0853", "0d1c2b6a7e90")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tool_call_event",
        sa.Column("tool_call_event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dialog_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tool_call_id", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["dialog_id"], ["dialog.dialog_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tool_call_event_id"),
        sqlite_autoincrement=True,
    )
    op.create_index("tool_call_event_dialog_id", "tool_call_event", ["dialog_id"], unique=False)
    op.create_index("tool_call_event_user_id", "tool_call_event", ["user_id"], unique=False)
    op.create_index("tool_call_event_tool_call_id", "tool_call_event", ["tool_call_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("tool_call_event_tool_call_id", table_name="tool_call_event")
    op.drop_index("tool_call_event_user_id", table_name="tool_call_event")
    op.drop_index("tool_call_event_dialog_id", table_name="tool_call_event")
    op.drop_table("tool_call_event")
