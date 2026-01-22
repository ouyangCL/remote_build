"""Add git_ssh_key to projects table, remove git_username and git_password

Revision ID: 006_add_git_ssh_key
Revises: 005_add_git_username_password
Create Date: 2026-01-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_git_ssh_key'
down_revision: Union[str, None] = '005_add_git_username_password'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add git_ssh_key column, remove git_username and git_password columns."""
    # Add new SSH key column
    op.add_column('projects', sa.Column('git_ssh_key', sa.Text, nullable=True))

    # Remove old username/password columns
    op.drop_column('projects', 'git_password')
    op.drop_column('projects', 'git_username')


def downgrade() -> None:
    """Restore git_username and git_password columns, remove git_ssh_key column."""
    # Add back username/password columns
    op.add_column('projects', sa.Column('git_username', sa.String(100), nullable=True))
    op.add_column('projects', sa.Column('git_password', sa.String(255), nullable=True))

    # Remove SSH key column
    op.drop_column('projects', 'git_ssh_key')
