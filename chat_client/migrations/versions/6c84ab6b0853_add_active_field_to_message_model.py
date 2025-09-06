"""Add active field to message model

Revision ID: 6c84ab6b0853
Revises: 25c189b7a41c
Create Date: 2025-09-06 15:14:39.026287

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c84ab6b0853'
down_revision: Union[str, None] = '25c189b7a41c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the active column with default value of 1 to the message table
    op.add_column('message', sa.Column('active', sa.Integer(), nullable=False, server_default='1'))
    # Set all existing messages to active=1 (this is redundant due to server_default but makes it explicit)
    op.execute("UPDATE message SET active = 1")


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the active column from the message table
    op.drop_column('message', 'active')