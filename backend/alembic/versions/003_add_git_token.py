"""Add git_token to projects table

Revision ID: 003_add_git_token
Revises: 002_add_environment_isolation
Create Date: 2026-01-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_git_token'
down_revision: Union[str, None] = '002_add_environment_isolation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add git_token column to projects table."""
    op.add_column('projects', sa.Column('git_token', sa.String(255), nullable=True))


def downgrade() -> None:
    """Remove git_token column from projects table."""
    op.drop_column('projects', 'git_token')
