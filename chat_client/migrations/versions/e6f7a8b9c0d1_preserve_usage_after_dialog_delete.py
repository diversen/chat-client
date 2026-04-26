"""Preserve usage rows after dialog deletion

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-04-26 13:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()

    op.create_table(
        "llm_usage_event_new",
        sa.Column("llm_usage_event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dialog_id", sa.String(), nullable=False),
        sa.Column("dialog_title", sa.Text(), nullable=False, server_default=""),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("llm_usage_event_id"),
        sqlite_autoincrement=True,
    )

    connection.execute(
        sa.text(
            """
            INSERT INTO llm_usage_event_new (
                llm_usage_event_id,
                dialog_id,
                dialog_title,
                user_id,
                turn_id,
                round_index,
                provider,
                model,
                call_type,
                request_id,
                input_tokens,
                cached_input_tokens,
                output_tokens,
                total_tokens,
                reasoning_tokens,
                input_price_per_million,
                cached_input_price_per_million,
                output_price_per_million,
                currency,
                cost_amount,
                usage_source,
                created
            )
            SELECT
                usage.llm_usage_event_id,
                usage.dialog_id,
                COALESCE(dialog.title, ''),
                usage.user_id,
                usage.turn_id,
                usage.round_index,
                usage.provider,
                usage.model,
                usage.call_type,
                usage.request_id,
                usage.input_tokens,
                usage.cached_input_tokens,
                usage.output_tokens,
                usage.total_tokens,
                usage.reasoning_tokens,
                usage.input_price_per_million,
                usage.cached_input_price_per_million,
                usage.output_price_per_million,
                usage.currency,
                usage.cost_amount,
                usage.usage_source,
                usage.created
            FROM llm_usage_event AS usage
            LEFT JOIN dialog ON dialog.dialog_id = usage.dialog_id
            """
        )
    )

    op.drop_index("llm_usage_event_dialog_turn_id", table_name="llm_usage_event")
    op.drop_index("llm_usage_event_user_id", table_name="llm_usage_event")
    op.drop_index("llm_usage_event_dialog_id", table_name="llm_usage_event")
    op.drop_table("llm_usage_event")
    op.rename_table("llm_usage_event_new", "llm_usage_event")
    op.create_index("llm_usage_event_dialog_id", "llm_usage_event", ["dialog_id"], unique=False)
    op.create_index("llm_usage_event_user_id", "llm_usage_event", ["user_id"], unique=False)
    op.create_index("llm_usage_event_dialog_turn_id", "llm_usage_event", ["dialog_id", "turn_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()

    op.create_table(
        "llm_usage_event_old",
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

    connection.execute(
        sa.text(
            """
            INSERT INTO llm_usage_event_old (
                llm_usage_event_id,
                dialog_id,
                user_id,
                turn_id,
                round_index,
                provider,
                model,
                call_type,
                request_id,
                input_tokens,
                cached_input_tokens,
                output_tokens,
                total_tokens,
                reasoning_tokens,
                input_price_per_million,
                cached_input_price_per_million,
                output_price_per_million,
                currency,
                cost_amount,
                usage_source,
                created
            )
            SELECT
                llm_usage_event_id,
                dialog_id,
                user_id,
                turn_id,
                round_index,
                provider,
                model,
                call_type,
                request_id,
                input_tokens,
                cached_input_tokens,
                output_tokens,
                total_tokens,
                reasoning_tokens,
                input_price_per_million,
                cached_input_price_per_million,
                output_price_per_million,
                currency,
                cost_amount,
                usage_source,
                created
            FROM llm_usage_event
            """
        )
    )

    op.drop_index("llm_usage_event_dialog_turn_id", table_name="llm_usage_event")
    op.drop_index("llm_usage_event_user_id", table_name="llm_usage_event")
    op.drop_index("llm_usage_event_dialog_id", table_name="llm_usage_event")
    op.drop_table("llm_usage_event")
    op.rename_table("llm_usage_event_old", "llm_usage_event")
    op.create_index("llm_usage_event_dialog_id", "llm_usage_event", ["dialog_id"], unique=False)
    op.create_index("llm_usage_event_user_id", "llm_usage_event", ["user_id"], unique=False)
    op.create_index("llm_usage_event_dialog_turn_id", "llm_usage_event", ["dialog_id", "turn_id"], unique=False)
