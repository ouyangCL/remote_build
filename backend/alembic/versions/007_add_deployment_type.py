"""Add deployment_type to deployments table

Revision ID: 007_add_deployment_type
Revises: 006_add_git_ssh_key
Create Date: 2026-01-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_deployment_type'
down_revision: Union[str, None] = '006_add_git_ssh_key'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deployment_type column to deployments table."""
    # Add deployment_type column with default value 'full'
    op.add_column('deployments', sa.Column('deployment_type', sa.String(20), nullable=False, server_default='full'))


def downgrade() -> None:
    """Remove deployment_type column from deployments table."""
    op.drop_column('deployments', 'deployment_type')
