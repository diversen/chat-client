"""Add llm_usage_event table

Revision ID: d4e5f6a7b8c9
Revises: b3f1c2d4e6a8
Create Date: 2026-04-26 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "b3f1c2d4e6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "llm_usage_event",
        sa.Column("llm_usage_event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dialog_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("round_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider", sa.Text(), nullable=False, server_default=""),
        sa.Column("model", sa.Text(), nullable=False, server_default=""),
        sa.Column("call_type", sa.Text(), nullable=False, server_default="chat"),
        sa.Column("request_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_price_per_million", sa.Text(), nullable=False, server_default="0"),
        sa.Column("cached_input_price_per_million", sa.Text(), nullable=False, server_default="0"),
        sa.Column("output_price_per_million", sa.Text(), nullable=False, server_default="0"),
        sa.Column("currency", sa.Text(), nullable=False, server_default="USD"),
        sa.Column("cost_amount", sa.Text(), nullable=False, server_default="0"),
        sa.Column("usage_source", sa.Text(), nullable=False, server_default="missing"),
        sa.Column("created", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["dialog_id"], ["dialog.dialog_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("llm_usage_event_id"),
        sqlite_autoincrement=True,
    )
    op.create_index("llm_usage_event_dialog_id", "llm_usage_event", ["dialog_id"], unique=False)
    op.create_index("llm_usage_event_user_id", "llm_usage_event", ["user_id"], unique=False)
    op.create_index("llm_usage_event_dialog_turn_id", "llm_usage_event", ["dialog_id", "turn_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("llm_usage_event_dialog_turn_id", table_name="llm_usage_event")
    op.drop_index("llm_usage_event_user_id", table_name="llm_usage_event")
    op.drop_index("llm_usage_event_dialog_id", table_name="llm_usage_event")
    op.drop_table("llm_usage_event")
