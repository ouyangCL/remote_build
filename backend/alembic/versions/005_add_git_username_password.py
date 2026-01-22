"""Add git_username and git_password to projects table, remove git_token

Revision ID: 005_add_git_username_password
Revises: 004_add_connection_status
Create Date: 2026-01-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_git_username_password'
down_revision: Union[str, None] = '004_add_connection_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add git_username and git_password columns, remove git_token column."""
    # Add new columns
    op.add_column('projects', sa.Column('git_username', sa.String(100), nullable=True))
    op.add_column('projects', sa.Column('git_password', sa.String(255), nullable=True))
    # Remove old token column
    op.drop_column('projects', 'git_token')


def downgrade() -> None:
    """Restore git_token column, remove git_username and git_password columns."""
    # Add back token column
    op.add_column('projects', sa.Column('git_token', sa.String(255), nullable=True))
    # Remove new columns
    op.drop_column('projects', 'git_password')
    op.drop_column('projects', 'git_username')
