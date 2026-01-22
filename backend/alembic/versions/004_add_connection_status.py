"""Add connection_status to servers table

Revision ID: 004_add_connection_status
Revises: 003_add_git_token
Create Date: 2026-01-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_connection_status'
down_revision: Union[str, None] = '003_add_git_token'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add connection_status column to servers table."""
    # Add the column with default value 'untested'
    op.add_column(
        'servers',
        sa.Column('connection_status', sa.String(20), nullable=False, server_default='untested')
    )


def downgrade() -> None:
    """Remove connection_status column from servers table."""
    op.drop_column('servers', 'connection_status')
