"""Add sequence_index to message and tool_call_event

Revision ID: 9f4a7b5c2d10
Revises: c8c5d9f58f2b
Create Date: 2026-03-01 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f4a7b5c2d10"
down_revision: Union[str, Sequence[str], None] = "c8c5d9f58f2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _role_rank(role: str) -> int:
    normalized = str(role or "").strip().lower()
    if normalized in {"user", "system"}:
        return 0
    if normalized == "tool":
        return 1
    if normalized == "assistant":
        return 2
    return 3


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("message", sa.Column("sequence_index", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tool_call_event", sa.Column("sequence_index", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("message_dialog_sequence_index", "message", ["dialog_id", "sequence_index"], unique=False)
    op.create_index("tool_call_event_dialog_sequence_index", "tool_call_event", ["dialog_id", "sequence_index"], unique=False)

    connection = op.get_bind()
    dialog_rows = connection.execute(sa.text("SELECT dialog_id FROM dialog")).fetchall()

    for row in dialog_rows:
        dialog_id = row[0]
        if not dialog_id:
            continue

        message_rows = connection.execute(
            sa.text(
                "SELECT message_id, role, created "
                "FROM message "
                "WHERE dialog_id = :dialog_id "
                "ORDER BY created ASC, message_id ASC"
            ),
            {"dialog_id": dialog_id},
        ).fetchall()

        tool_rows = connection.execute(
            sa.text(
                "SELECT tool_call_event_id, created "
                "FROM tool_call_event "
                "WHERE dialog_id = :dialog_id "
                "ORDER BY created ASC, tool_call_event_id ASC"
            ),
            {"dialog_id": dialog_id},
        ).fetchall()

        merged: list[tuple[str, int, int, str]] = []
        for message_id, role, created in message_rows:
            merged.append((str(created), _role_rank(str(role)), int(message_id), "message"))
        for tool_call_event_id, created in tool_rows:
            merged.append((str(created), _role_rank("tool"), int(tool_call_event_id), "tool_call_event"))

        merged.sort(key=lambda item: (item[0], item[1], item[2]))

        for index, (_created, _rank, row_id, table_name) in enumerate(merged, start=1):
            if table_name == "message":
                connection.execute(
                    sa.text("UPDATE message SET sequence_index = :index WHERE message_id = :row_id"),
                    {"index": index, "row_id": row_id},
                )
            else:
                connection.execute(
                    sa.text("UPDATE tool_call_event SET sequence_index = :index WHERE tool_call_event_id = :row_id"),
                    {"index": index, "row_id": row_id},
                )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("tool_call_event_dialog_sequence_index", table_name="tool_call_event")
    op.drop_index("message_dialog_sequence_index", table_name="message")
    op.drop_column("tool_call_event", "sequence_index")
    op.drop_column("message", "sequence_index")
