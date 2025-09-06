"""Add active field to message table

Revision ID: c3632955879d
Revises: 25c189b7a41c
Create Date: 2025-09-06 14:24:49.585025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3632955879d'
down_revision: Union[str, None] = '25c189b7a41c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add active column with default value 1
    op.add_column('message', sa.Column('active', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('message', 'active')