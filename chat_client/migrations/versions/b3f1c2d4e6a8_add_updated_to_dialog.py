"""Add updated column to dialog

Revision ID: b3f1c2d4e6a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-25 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3f1c2d4e6a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("dialog", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "updated",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            )
        )
        batch_op.create_index("dialog_user_id_updated", ["user_id", "updated"], unique=False)

    op.execute(sa.text("UPDATE dialog SET updated = created"))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("dialog", recreate="always") as batch_op:
        batch_op.drop_index("dialog_user_id_updated")
        batch_op.drop_column("updated")
